#!/usr/bin/env bash
# Runs restart-reset's jq filter, read from the rendered CronJob, over fixture lists.
# Run `just configure` first: this reads the render, not the template.
set -euo pipefail

cronjob=kubernetes/apps/kube-system/restart-reset/app/cronjob.yaml
filter="$(yq '.spec.jobTemplate.spec.template.spec.containers[0].args[0]' "$cronjob" | awk "/^jq -r/ { on = 1; next } /^'/ { on = 0 } on")"
[[ -n $filter ]] || {
    echo "no jq filter found in $cronjob"
    exit 1
}
failed=0

# check <name> <want> <objects as JSON, comma separated>
check() {
    local got
    got="$(jq -r --argjson now 100000 "$filter" <<<"{\"items\": [$3]}")"
    if [[ $got == "$2" ]]; then
        echo "ok $1"
    else
        echo "FAILED $1: want [$2] got [$got]"
        failed=1
    fi
}

# A Running pod with one restart long ago: pod <name> <owner kind> <owner> [ready] [labels]
pod() {
    jq -nc --arg name "$1" --arg kind "$2" --arg owner "$3" --argjson ready "${4:-true}" --argjson labels "${5:-{\}}" '{
        kind: "Pod",
        metadata: {namespace: "ns", name: $name, labels: $labels, ownerReferences: [{kind: $kind, name: $owner, controller: true}]},
        status: {phase: "Running", containerStatuses: [{ready: $ready, restartCount: 1, lastState: {terminated: {finishedAt: "1970-01-01T00:00:00Z"}}}]}
    }'
}
pdb() { jq -nc --arg ns "$1" --argjson selector "$2" '{kind: "PodDisruptionBudget", metadata: {namespace: $ns, name: "web"}, spec: {selector: $selector}}'; }

rs='{"kind":"ReplicaSet","metadata":{"namespace":"ns","name":"web-1","ownerReferences":[{"kind":"Deployment","name":"web"}]}}'
two="$rs,{\"kind\":\"Deployment\",\"metadata\":{\"namespace\":\"ns\",\"name\":\"web\"},\"spec\":{\"replicas\":2}}"
one="$rs,{\"kind\":\"Deployment\",\"metadata\":{\"namespace\":\"ns\",\"name\":\"web\"},\"spec\":{\"replicas\":1}}"
web='{"app":"web"}'
primary='{"cnpg.io/instanceRole":"primary"}'
replica='{"cnpg.io/instanceRole":"replica"}'
recent="$(pod web-a ReplicaSet web-1 | jq -c '.status.containerStatuses[0].lastState.terminated.finishedAt = "1970-01-02T03:46:00Z"')"

check "two Ready replicas yield one pod" "ns web-a Deployment web" "$two,$(pod web-a ReplicaSet web-1),$(pod web-b ReplicaSet web-1)"
check "one replica without a PDB yields nothing" "" "$one,$(pod web-a ReplicaSet web-1)"
check "one replica with a matching PDB yields the pod" "ns web-a Deployment web" "$one,$(pod web-a ReplicaSet web-1 true "$web"),$(pdb ns '{"matchLabels":{"app":"web"}}')"
check "a PDB in another namespace does not count" "" "$one,$(pod web-a ReplicaSet web-1 true "$web"),$(pdb other '{"matchLabels":{"app":"web"}}')"
check "a PDB with no selector does not count" "" "$one,$(pod web-a ReplicaSet web-1 true "$web"),$(pdb ns null)"
check "a matchExpressions PDB does not count" "" "$one,$(pod web-a ReplicaSet web-1 true "$web"),$(pdb ns '{"matchExpressions":[{"key":"app","operator":"Exists"}]}')"
check "two replicas with one not Ready yield nothing" "" "$two,$(pod web-a ReplicaSet web-1),$(pod web-b ReplicaSet web-1 false)"
for kind in StatefulSet DaemonSet Node Job; do
    check "a $kind pod yields nothing" "" "$(pod x "$kind" owner)"
done
check "a CNPG replica yields the pod, its primary does not" "ns pg-2 Cluster pg" "$(pod pg-1 Cluster pg true "$primary"),$(pod pg-2 Cluster pg true "$replica")"
check "a CNPG cluster with an unready instance yields nothing" "" "$(pod pg-1 Cluster pg true "$primary"),$(pod pg-2 Cluster pg false "$replica"),$(pod pg-3 Cluster pg true "$replica")"
check "a one-instance CNPG cluster yields nothing" "" "$(pod pg-1 Cluster pg true "$primary")"
check "a recent restart is left alone, the older sibling goes" "ns web-b Deployment web" "$two,$recent,$(pod web-b ReplicaSet web-1)"

exit "$failed"
