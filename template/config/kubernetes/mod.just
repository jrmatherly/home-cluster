set quiet
set shell := ['bash', '-euo', 'pipefail', '-c']
set script-interpreter := ['bash', '-euo', 'pipefail']
set default-list
set default-script

[doc('Force Flux to pull in changes from your Git repository')]
[group('kube')]
reconcile:
    flux --namespace flux-system reconcile kustomization flux-system --with-source

[doc('List every CloudNativePG primary and the node it runs on')]
[group('kube')]
primaries:
    kubectl get pods -A -l cnpg.io/instanceRole=primary \
        -o custom-columns='NAMESPACE:.metadata.namespace,CLUSTER:.metadata.labels.cnpg\.io/cluster,POD:.metadata.name,NODE:.spec.nodeName'

[confirm("Switch " + cluster + " over to a replica? Writes are refused for about 16 seconds. [y/N]")]
[doc('Promote a CloudNativePG replica to primary (default: a Ready replica on another node) and wait for a healthy cluster')]
[group('kube')]
switchover cluster namespace replica='':
    cluster_json="$(kubectl get clusters.postgresql.cnpg.io -n "{{ namespace }}" "{{ cluster }}" -o json)"
    primary="$(jq -r '.status.currentPrimary' <<<"$cluster_json")"
    replica="{{ replica }}"
    if [[ -z $replica ]]; then
        primary_node="$(kubectl get pod -n "{{ namespace }}" "$primary" -o jsonpath='{.spec.nodeName}')"
        replica="$(kubectl get pods -n "{{ namespace }}" -l "cnpg.io/cluster={{ cluster }},cnpg.io/instanceRole=replica" --field-selector "spec.nodeName!=$primary_node" -o json | jq -r '[.items[] | select(any(.status.conditions[]?; .type == "Ready" and .status == "True")) | .metadata.name][0] // empty')"
        [[ -n $replica ]] || just log fatal "No Ready replica on another node to promote" cluster "{{ cluster }}" namespace "{{ namespace }}"
    fi
    if [[ $primary == "$replica" ]]; then
        just log info "Already the primary" cluster "{{ cluster }}" primary "$primary"
        exit 0
    fi
    instances="$(jq -r '.spec.instances' <<<"$cluster_json")"
    just log info "Promoting" cluster "{{ cluster }}" from "$primary" to "$replica"
    kubectl cnpg promote "{{ cluster }}" "$replica" -n "{{ namespace }}"
    want="Cluster in healthy state|$replica|$instances"
    deadline=$((SECONDS + 180))
    until state="$(kubectl get clusters.postgresql.cnpg.io -n "{{ namespace }}" "{{ cluster }}" -o jsonpath='{.status.phase}|{.status.currentPrimary}|{.status.readyInstances}')" && [[ $state == "$want" ]]; do
        (( SECONDS < deadline )) || just log fatal "Timed out waiting for the switchover: $state" cluster "{{ cluster }}"
        just log info "Waiting for the switchover: ${state%%|*}" cluster "{{ cluster }}"
        sleep 5
    done
    just log info "Switchover done" cluster "{{ cluster }}" primary "$replica"
