set quiet
set shell := ['bash', '-euo', 'pipefail', '-c']
set script-interpreter := ['bash', '-euo', 'pipefail']
set default-list
set default-script

# Day-2 apply/upgrade recipes rely on topf's built-in diff-and-confirm
# prompt; only the destructive reset recipes disable it in favour of just's
# own confirmation.

[doc('Apply Talos config to all nodes (shows a diff and asks first)')]
[group('talos')]
apply:
    topf apply

[arg('mode', pattern='auto|reboot|no-reboot|staged|try')]
[doc('Apply Talos config to a node (shows a diff and asks first)')]
[group('talos')]
apply-node node mode='auto':
    topf apply --nodes-filter "^{{ node }}$" --mode "{{ mode }}"

[doc('Show pending config changes without applying them')]
[group('talos')]
diff:
    topf apply --dry-run

[confirm("Drain node " + node + "? Its CloudNativePG primaries switch over first. [y/N]")]
[doc('Drain a node: preflight checks, CloudNativePG switchover, then kubectl drain')]
[group('talos')]
drain node:
    info="$(just talos node-info "{{ node }}")"
    read -r _ role <<<"$info"
    # A node that is NotReady and cordoned was taken down on purpose (an earlier stop-node on the
    # same host); one that is NotReady and schedulable is a failure, and draining another is how
    # quorum goes.
    just log info "Preflight: every other node is Ready, or cordoned on purpose" node "{{ node }}"
    nodes="$(kubectl get nodes -o json)"
    not_ready="$(jq -r --arg n "{{ node }}" '[.items[] | select(.metadata.name != $n) | select(any(.status.conditions[]; .type == "Ready" and .status == "True") | not) | select(.spec.unschedulable != true) | .metadata.name] | join(",")' <<<"$nodes")"
    [[ -z $not_ready ]] || just log fatal "Nodes are not Ready and not cordoned" nodes "$not_ready"
    down="$(jq -r --arg n "{{ node }}" '[.items[] | select(.metadata.name != $n) | select(.spec.unschedulable == true) | .metadata.name] | join(",")' <<<"$nodes")"
    [[ -z $down ]] || just log warn "Nodes already cordoned" nodes "$down"
    if [[ $role == control-plane ]]; then
        just log info "Preflight: the other control planes are Ready, schedulable, and serving etcd"
        while read -r cp_host cp_ip; do
            [[ ",$down," != *",$cp_host,"* ]] || just log fatal "Control plane is cordoned; draining {{ node }} would lose quorum" node "$cp_host"
            talosctl -n "$cp_ip" etcd status >/dev/null || just log fatal "etcd is not serving on a control plane; draining {{ node }} would lose quorum" node "$cp_host"
        done < <(yq '.nodes[] | select(.role == "control-plane" and .host != "{{ node }}") | .host + " " + .ip' topf.yaml)
        want="$(yq '[.nodes[] | select(.role == "control-plane")] | length' topf.yaml)"
        members="$(talosctl -n "$(yq '[.nodes[] | select(.role == "control-plane" and .host != "{{ node }}")][0].ip' topf.yaml)" etcd members | awk 'NR > 1 && $NF == "false" { c++ } END { print c + 0 }')"
        [[ $members == "$want" ]] || just log fatal "etcd does not have every control plane as a voting member" members "$members" want "$want"
    fi
    just log info "Switching over CloudNativePG primaries" node "{{ node }}"
    primaries="$(kubectl get pods -A -l cnpg.io/instanceRole=primary --field-selector "spec.nodeName={{ node }}" -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.labels.cnpg\.io/cluster} {end}')"
    for p in $primaries; do
        ns="${p%%/*}"
        cluster="${p#*/}"
        just --yes kube switchover "$cluster" "$ns"
    done
    just log info "Draining" node "{{ node }}"
    kubectl drain "{{ node }}" --ignore-daemonsets --delete-emptydir-data --timeout=5m
    just log info "Pods pinned to the node (stay Pending until it returns)"
    just talos pinned "{{ node }}" | column -t -s $'\t'

[doc('Check Talos, nodes, pods, Flux and CloudNativePG; fails when a node or Flux object is not Ready')]
[group('talos')]
health:
    rc=0
    cp="$(yq '[.nodes[] | select(.role == "control-plane")][0].ip' topf.yaml)"
    just log info "Talos health" node "$cp"
    talosctl health --server=false -n "$cp" --wait-timeout=5m || rc=1
    just log info "Nodes"
    kubectl get nodes
    kubectl wait nodes --all --for=condition=Ready --timeout=0s >/dev/null || rc=1
    just log info "Pods not fully Ready"
    kubectl get pods -A -o json | jq -r '["NAMESPACE", "POD", "PHASE", "NODE"], (.items[] | select(.status.phase != "Succeeded") | select(.status.containerStatuses == null or any(.status.containerStatuses[]; .ready | not)) | [.metadata.namespace, .metadata.name, .status.phase, (.spec.nodeName // "-")]) | @tsv' | column -t -s $'\t'
    for kind in ks hr; do
        just log info "Flux $kind not Ready"
        bad="$(flux get "$kind" -A --no-header | awk -F'\t' '{ r = $5; gsub(/ /, "", r) } r != "True"')"
        if [[ -n $bad ]]; then
            printf '%s\n' "$bad"
            rc=1
        fi
    done
    just log info "CloudNativePG clusters"
    kubectl get clusters.postgresql.cnpg.io -A
    exit "$rc"

[doc('List all nodes and their current state')]
[group('talos')]
nodes:
    topf nodes

[private]
node-info node:
    if ! yq -e '.nodes[] | select(.host == "{{ node }}") | .ip + " " + .role' topf.yaml 2>/dev/null; then
        just log fatal "Unknown node" node "{{ node }}" known "$(yq '[.nodes[].host] | join(",")' topf.yaml)"
    fi

# Pods that cannot run on another node: pinned by a hostname nodeSelector, by a
# local volume whose PV is bound to this node, or by a GPU only this node has. TSV with a header.
[private]
pinned node:
    printf 'NAMESPACE\tPOD\tPHASE\tPINNED BY\n'
    pvcs="$(kubectl get pv -o json | jq -c --arg n "{{ node }}" '[.items[] | select(any(.spec.nodeAffinity.required.nodeSelectorTerms[]?.matchExpressions[]?; .key == "kubernetes.io/hostname" and any(.values[]; . == $n))) | .spec.claimRef | "\(.namespace)/\(.name)"]')"
    gpu_nodes="$(kubectl get nodes -o json | jq -c '[.items[] | select(.status.allocatable["nvidia.com/gpu"] != null) | .metadata.name]')"
    kubectl get pods -A -o json | jq -r --arg n "{{ node }}" --argjson pvcs "$pvcs" --argjson gpu_nodes "$gpu_nodes" '
        .items[] | select(.status.phase == "Running" or .status.phase == "Pending")
        | .metadata.namespace as $ns
        | [.spec.volumes[]?.persistentVolumeClaim.claimName // empty | "\($ns)/\(.)" | select(IN($pvcs[]))] as $vols
        | (any(.spec.containers[]; .resources.limits["nvidia.com/gpu"] != null) and $gpu_nodes == [$n]) as $gpu
        | (if .spec.nodeSelector["kubernetes.io/hostname"] == $n then "nodeSelector"
           elif ($vols | length) > 0 then "volume:" + ($vols | map(split("/")[1]) | join(","))
           elif $gpu then "gpu"
           else empty end) as $why
        | [$ns, .metadata.name, .status.phase, $why] | @tsv'

[confirm("Drain and reboot node " + node + "? [y/N]")]
[doc('Drain a node, reboot Talos, wait for it to return, then resume it')]
[group('talos')]
reboot-node node:
    info="$(just talos node-info "{{ node }}")"
    read -r ip _ <<<"$info"
    just --yes talos drain "{{ node }}"
    boot_id="$(kubectl get node "{{ node }}" -o jsonpath='{.status.nodeInfo.bootID}')"
    just log info "Rebooting" node "{{ node }}"
    talosctl -n "$ip" reboot --wait=false
    # A new boot ID proves the reboot happened even if NotReady was never observed; resume waits for Ready.
    deadline=$((SECONDS + 600))
    until id="$(kubectl get node "{{ node }}" -o jsonpath='{.status.nodeInfo.bootID}')" && [[ -n $id && $id != "$boot_id" ]]; do
        (( SECONDS < deadline )) || just log fatal "Timed out waiting for the node to reboot" node "{{ node }}"
        sleep 10
    done
    just talos resume "{{ node }}"

[doc('Render Talos machine configs to ./rendered')]
[group('talos')]
render:
    topf render --output ./rendered

[confirm("This will destroy your cluster and reset all nodes to maintenance mode — continue? [y/N]")]
[doc('Reset all nodes back to maintenance mode (DESTRUCTIVE)')]
[group('talos')]
reset:
    topf reset --confirm=false

[confirm("This will reset node " + node + " to maintenance mode — continue? [y/N]")]
[doc('Reset a single node back to maintenance mode (DESTRUCTIVE)')]
[group('talos')]
reset-node node:
    topf reset --nodes-filter "^{{ node }}$" --confirm=false

[doc('Bring a node back after maintenance: wait for Ready and etcd, uncordon, wait for its pods')]
[group('talos')]
resume node:
    info="$(just talos node-info "{{ node }}")"
    read -r ip role <<<"$info"
    just log info "Waiting for the node to be Ready" node "{{ node }}"
    kubectl wait "node/{{ node }}" --for=condition=Ready --timeout=10m
    if [[ $role == control-plane ]]; then
        just log info "Waiting for etcd" node "{{ node }}"
        deadline=$((SECONDS + 600))
        until talosctl -n "$ip" etcd status &>/dev/null; do
            (( SECONDS < deadline )) || just log fatal "Timed out waiting for etcd" node "{{ node }}"
            sleep 10
        done
    fi
    just talos uncordon "{{ node }}"
    # Not `just talos health` here: its Talos check waits up to 5 minutes while any other node
    # is still cordoned, which is the normal state between resumes on a multi-node host. Run it
    # once at the end of the runbook.
    kubectl get nodes

[doc('Show what taking a node down affects')]
[group('talos')]
status node:
    info="$(just talos node-info "{{ node }}")"
    read -r ip role <<<"$info"
    just log info "Node" node "{{ node }}" ip "$ip" role "$role"
    kubectl get node "{{ node }}"
    just log info "Pods that move when the node drains (DaemonSet and static pods left out)"
    kubectl get pods -A --field-selector "spec.nodeName={{ node }},status.phase!=Succeeded" -o json \
        | jq -r '["NAMESPACE", "POD", "PHASE"], (.items[] | select(any(.metadata.ownerReferences[]?; .kind == "DaemonSet" or .kind == "Node") | not) | [.metadata.namespace, .metadata.name, .status.phase]) | @tsv' \
        | column -t -s $'\t'
    just log info "CloudNativePG primaries (switched over by drain)"
    kubectl get pods -A -l cnpg.io/instanceRole=primary --field-selector "spec.nodeName={{ node }}"
    just log info "Pods pinned to the node (stay Pending until it returns)"
    just talos pinned "{{ node }}" | column -t -s $'\t'
    if [[ $role == control-plane ]]; then
        just log info "etcd"
        talosctl -n "$ip" etcd status
    fi

[confirm("Drain and shut down node " + node + "? [y/N]")]
[doc('Drain a node and power it off for host maintenance')]
[group('talos')]
stop-node node:
    info="$(just talos node-info "{{ node }}")"
    read -r ip _ <<<"$info"
    state="$(kubectl get node "{{ node }}" -o jsonpath='{.spec.unschedulable} {.status.conditions[?(@.type=="Ready")].status}')"
    if [[ $state == "true False" || $state == "true Unknown" ]]; then
        just log warn "Node is already cordoned and NotReady; skipping the drain" node "{{ node }}"
    else
        just --yes talos drain "{{ node }}"
    fi
    just log info "Shutting down" node "{{ node }}"
    talosctl -n "$ip" shutdown --wait=false || just log warn "Talos API did not answer; the node may already be off" node "{{ node }}"
    deadline=$((SECONDS + 300))
    while talosctl -n "$ip" version --short &>/dev/null; do
        (( SECONDS < deadline )) || just log fatal "Timed out waiting for the Talos API to stop" node "{{ node }}"
        sleep 10
    done
    just log info "Talos API is down; confirm the VM is stopped on the host (qm status), reboot the host, then run: just talos resume {{ node }}"

[doc('Uncordon a node and wait for its pods to be Ready')]
[group('talos')]
uncordon node:
    just talos node-info "{{ node }}" >/dev/null
    kubectl uncordon "{{ node }}"
    just log info "Waiting for pods on the node to be Ready" node "{{ node }}"
    deadline=$((SECONDS + 600))
    # The reads sit in the loop body, not its condition, so a failing kubectl aborts the recipe
    # instead of reading as "no pods left to wait for".
    while true; do
        on_node="$(kubectl get pods -A --field-selector "spec.nodeName={{ node }}" -o json | jq -r '.items[] | select(.status.phase == "Running" or .status.phase == "Pending") | select(any(.status.conditions[]?; .type == "Ready" and .status == "True") | not) | "\(.metadata.namespace)/\(.metadata.name)"')"
        pinned="$(just talos pinned "{{ node }}" | awk -F'\t' '$3 == "Pending" { print $1 "/" $2 }')"
        waiting="$(printf '%s\n' $on_node $pinned | sed '/^$/d' | sort -u | paste -sd, -)"
        [[ -n $waiting ]] || break
        (( SECONDS < deadline )) || just log fatal "Timed out waiting for pods" pods "$waiting"
        just log info "Waiting for pods" pods "$waiting"
        sleep 10
    done
    kubectl get node "{{ node }}"

# topf intentionally does not manage Kubernetes upgrades
[doc('Upgrade Kubernetes')]
[group('talos')]
upgrade-k8s:
    talosctl --nodes "$(yq '[.nodes[] | select(.role == "control-plane")][0].ip' topf.yaml)" \
        upgrade-k8s --to "$(yq '.kubernetesVersion' topf.yaml)"

[doc('Upgrade Talos on all nodes, one at a time (asks first)')]
[group('talos')]
upgrade:
    topf upgrade

[doc('Upgrade Talos on a single node (asks first)')]
[group('talos')]
upgrade-node node:
    topf upgrade --nodes-filter "^{{ node }}$"
