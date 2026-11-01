#!/usr/bin/env bash
# Behaviour test for auto-merge.sh. Fake gh, kubectl, flux, git, flate, curl and sleep sit first on
# PATH, log their arguments to $LOG and answer from the fixtures in $FIX. One case per rule.
# usage: test-auto-merge.sh
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
script=$here/auto-merge.sh
work=$(mktemp -d "${TMPDIR:-/tmp}/auto-merge-test.XXXXXX")
trap 'rm -rf "$work"' EXIT
bin=$work/bin
mkdir -p "$bin"
export FIX LOG
oid_a=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
oid_b=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
merged=cccccccccccccccccccccccccccccccccccccccc
fake_token=ghp_$(printf 'a%.0s' {1..36})

cat >"$bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >>"$LOG"
case "$1 $2" in
    "pr view") cat "$FIX/pr-$3.json" ;;
    "pr diff") cat "$FIX/pr-$3.diff" ;;
esac
EOF
cat >"$bin/git" <<'EOF'
#!/usr/bin/env bash
echo "git $*" >>"$LOG"
case "$1" in
    merge-base) [[ -e "$FIX/on-main-${*: -1}" ]] ;;
    rev-parse) echo 1111111111111111111111111111111111111111 ;;
    log) cat "$FIX/reverts" 2>/dev/null || true ;;
esac
EOF
cat >"$bin/kubectl" <<'EOF'
#!/usr/bin/env bash
echo "kubectl $*" >>"$LOG"
for arg in "$@"; do
    [[ -f "$FIX/kubectl-fail" ]] && grep -qxF -- "$arg" "$FIX/kubectl-fail" && exit 1
done
exit 0
EOF
cat >"$bin/flux" <<'EOF'
#!/usr/bin/env bash
echo "flux $*" >>"$LOG"
[[ "$1" == get ]] || exit 0
echo "NAMESPACE NAME REVISION SUSPENDED READY MESSAGE"
# The nth listing of a kind prints unready-<kind>-<n>, so a case can change it across the merge.
cat "$FIX/unready-$2-$(grep -c "^flux get $2 " "$LOG")" 2>/dev/null || true
EOF
cat >"$bin/flate" <<'EOF'
#!/usr/bin/env bash
echo "flate $*" >>"$LOG"
cat "$FIX/flate.txt"
EOF
for fake in curl sleep; do
    cat >"$bin/$fake" <<EOF
#!/usr/bin/env bash
echo "$fake \$*" >>"\$LOG"
echo ok
EOF
done
chmod +x "$bin"/*
export PATH="$bin:$PATH"

# pr_fixture <pr> <app> <from> <to> <oid> <state> writes pr-N.json and a version-only diff. $rollup
# replaces the passing statusCheckRollup.
pr_fixture() {
    local pr=$1 app=$2 from=$3 to=$4 oid=$5 state=$6
    local default_rollup='[{"__typename":"CheckRun","name":"Flate","conclusion":"SUCCESS"},{"__typename":"StatusContext","context":"renovate/stability-days","state":"SUCCESS"}]'
    cat >"$FIX/pr-$pr.json" <<EOF
{"state":"$state","headRefOid":"$oid","mergeCommit":{"oid":"$merged"},
 "statusCheckRollup":${rollup:-$default_rollup},
 "author":{"is_bot":true,"login":"${author:-app/renovate}"},"isCrossRepository":${cross:-false},
 "headRefName":"${branch:-renovate/$app}","comments":[]}
EOF
    for file in kubernetes/apps/$app/$app/app/helmrelease.yaml template/config/kubernetes/apps/$app/$app/app/helmrelease.yaml.j2; do
        cat <<EOF
--- a/$file
+++ b/$file
@@ -1,1 +1,1 @@
-              tag: $from@sha256:1111111111111111111111111111111111111111111111111111111111111111
+              tag: $to@sha256:2222222222222222222222222222222222222222222222222222222222222222
EOF
    done >"$FIX/pr-$pr.diff"
}

# verdict <pr> <app> <from> <to> <oid> <verdict> prints one verdict object.
verdict() {
    printf '{"pr":%s,"app":"%s","namespace":"%s","kind":"image","from":"%s","to":"%s","bump":"patch","headRefOid":"%s","verdict":"%s","evidence":"test"}' \
        "$1" "$2" "$2" "$3" "$4" "$5" "$6"
}

fails=0
case_start() {
    FIX=$work/$1
    LOG=$FIX/log
    mkdir -p "$FIX"
    : >"$LOG"
    printf '  ✓  HelmRelease     kener/kener\n' >"$FIX/flate.txt"
    export CLUSTER_DOMAIN=example.test
}
run() { bash "$script" "$@" >"$FIX/out" 2>"$FIX/err" && echo 0 || echo $?; }
assert() {
    if ! eval "$2"; then
        echo "FAIL $1: $2"
        sed 's/^/    log: /' "$LOG"
        sed 's/^/    out: /' "$FIX/out"
        sed 's/^/    err: /' "$FIX/err"
        fails=$((fails + 1))
    fi
}
logged() { grep -qF -- "$1" "$LOG"; }

case_start safe-listed
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "safe listed app merges the researched head" "logged 'gh pr merge 69 --rebase --delete-branch --match-head-commit $oid_a'"
assert "safe listed app waits for the merge commit on the cluster" "logged 'kustomization/flux-system --for=jsonpath={.status.lastAppliedRevision}=refs/heads/main@sha1:$merged'"
assert "safe listed app waits for the HelmRelease" "logged 'wait helmrelease/kener --for=condition=Ready'"
assert "safe listed app runs its own checks" "logged 'curl -fsS https://status.example.test/healthcheck'"
assert "safe listed app writes nothing to Flux objects" "! logged 'flux reconcile' && ! logged 'kubectl annotate' && ! logged 'kubectl patch'"
assert "safe listed app exits 0" "[[ $status == 0 ]]"
assert "safe listed app reports merged and passed" "grep -q '^#69 kener 4.1.8 -> 4.1.9: merged, checks passed' '$FIX/out'"
assert "safe listed app does not run flate when the head is on main" "! logged 'flate '"

case_start helmrelease-wait-fails
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
echo helmrelease/kener >"$FIX/kubectl-fail"
touch "$FIX/on-main-$oid_a"
status=$(run "$FIX/verdicts.json")
assert "a failed HelmRelease wait reverts the merge" "logged 'revert --no-edit $merged'"
assert "a failed HelmRelease wait is reported as reverted" "grep -q 'a check failed, merge .* reverted' '$FIX/out'"
assert "a failed HelmRelease wait exits non-zero" "[[ $status != 0 ]]"

for flux_kind in hr ks; do
    case_start "cluster-not-ready-before-merge-$flux_kind"
    pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
    echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
    touch "$FIX/on-main-$oid_a"
    echo "media sonarr v1 False False dependency not ready, 2m" >"$FIX/unready-$flux_kind-1"
    echo "media sonarr v1 False False health check failed, 9m" >"$FIX/unready-$flux_kind-2"
    status=$(run "$FIX/verdicts.json")
    assert "$flux_kind not Ready before the merge does not revert it" "! logged 'revert --no-edit'"
    assert "$flux_kind not Ready before the merge reports passed" "grep -q '^#69 kener 4.1.8 -> 4.1.9: merged, checks passed' '$FIX/out'"

    case_start "cluster-not-ready-after-merge-$flux_kind"
    pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
    echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
    touch "$FIX/on-main-$oid_a"
    echo "media sonarr v1 False False dependency not ready, 2m" >"$FIX/unready-$flux_kind-1"
    printf 'media sonarr v1 False False dependency not ready, 3m\nmedia radarr v1 False False failed, 1m\n' >"$FIX/unready-$flux_kind-2"
    status=$(run "$FIX/verdicts.json")
    assert "$flux_kind newly not Ready after the merge reverts it" "logged 'revert --no-edit $merged'"
    assert "$flux_kind newly not Ready after the merge names the object" "grep -q 'media/radarr' '$FIX/err'"
done

case_start never-automerged
pr_fixture 92 pegaprox 1.4.0 1.4.1 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
echo "[$(verdict 92 pegaprox 1.4.0 1.4.1 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "pegaprox is commented, not merged" "logged 'gh pr comment 92' && ! logged 'gh pr merge'"
assert "pegaprox comment opens with the marker" "grep -q -- '--body <!-- update-apps verdict -->' '$LOG'"
assert "pegaprox is reported as commented" "grep -q '^#92 pegaprox 1.4.0 -> 1.4.1: commented' '$FIX/out'"
assert "pegaprox exits 0" "[[ $status == 0 ]]"

case_start non-tag-diff
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
printf -- '--- a/kubernetes/apps/kener/kener/app/helmrelease.yaml\n+++ b/kubernetes/apps/kener/kener/app/helmrelease.yaml\n@@ -1,1 +1,1 @@\n-  replicas: 1\n+  replicas: 2\n' >>"$FIX/pr-69.diff"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a non-version line is commented, not merged" "logged 'gh pr comment 69' && ! logged 'gh pr merge'"
assert "a non-version line exits 0" "[[ $status == 0 ]]"

case_start outside-kubernetes
pr_fixture 68 kener 32.0.1 32.0.2 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
sed -i.bak 's#kubernetes/apps/kener/kener/app/helmrelease.yaml#bootstrap/helmfile/crds.yaml#' "$FIX/pr-68.diff"
echo "[$(verdict 68 kener 32.0.1 32.0.2 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a file outside kubernetes/ is commented, not merged" "logged 'gh pr comment 68' && ! logged 'gh pr merge'"

case_start other-app-dir
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
sed -i.bak 's#kubernetes/apps/kener/kener/#kubernetes/apps/kener/sidecar/#' "$FIX/pr-69.diff"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a version line in another app's directory is commented, not merged" "logged 'gh pr comment 69' && ! logged 'gh pr merge'"

case_start shared-app-dir
pr_fixture 90 clickhouse 26.9.25.15 26.10.2.103 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
sed -i.bak 's#apps/clickhouse/clickhouse/#apps/langfuse/langfuse/#' "$FIX/pr-90.diff"
printf '[%s]' "$(verdict 90 clickhouse 26.9.25.15 26.10.2.103 "$oid_a" safe | sed 's/"namespace":"clickhouse"/"namespace":"langfuse"/')" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "an app living in another app's directory (dir:) merges" "logged 'gh pr merge 90 --rebase'"
assert "an app living in another app's directory waits on its StatefulSet" "logged 'rollout status sts/clickhouse'"

case_start foreign-author
author=someone pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a PR not opened by the Renovate app is commented, not merged" "logged 'gh pr comment 69' && ! logged 'gh pr merge' && ! logged 'gh pr diff'"

case_start cross-repository
cross=true pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a fork PR is commented, not merged" "logged 'gh pr comment 69' && ! logged 'gh pr merge'"

case_start foreign-branch
branch=feature/x pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a branch outside renovate/ is commented, not merged" "logged 'gh pr comment 69' && ! logged 'gh pr merge'"

case_start head-off-main
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a head behind main runs flate on a worktree first" "logged 'git worktree add' && logged 'flate test all' && logged 'gh pr merge 69'"
assert "flate runs before the merge" "[[ \$(grep -n 'flate test all' '$LOG' | cut -d: -f1) -lt \$(grep -n 'gh pr merge' '$LOG' | cut -d: -f1) ]]"
assert "flate is scoped to the namespace" "logged ' -n kener'"
assert "head behind main exits 0" "[[ $status == 0 ]]"

case_start flate-fails
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
printf '  ✗  HelmRelease     kener/kener  helm template: boom\n' >"$FIX/flate.txt"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a flate failure is commented, not merged" "logged 'gh pr comment 69' && ! logged 'gh pr merge'"

case_start failed-check
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
pr_fixture 70 reactive-resume v6.0.5 v6.0.6 "$oid_b" OPEN
touch "$FIX/on-main-$oid_a" "$FIX/on-main-$oid_b"
echo kener >"$FIX/kubectl-fail"
echo "[$(verdict 70 reactive-resume v6.0.5 v6.0.6 "$oid_b" safe),$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a failed check reverts the merge commit" "logged 'revert --no-edit $merged' && logged 'git push origin HEAD:main'"
assert "a failed check is commented" "logged 'gh pr comment 69'"
assert "a failed check exits non-zero" "[[ $status != 0 ]]"
assert "a later app stays unmerged" "! logged 'gh pr merge 70'"
assert "the stop is reported" "grep -q '^Stopped on: #69 kener' '$FIX/out'"
assert "kener merges before reactive-resume whatever the verdict order" "! logged 'gh pr view 70'"

flate_ok='{"__typename":"CheckRun","name":"Flate","conclusion":"SUCCESS"}'
for unfinished in \
    "failure|[{\"__typename\":\"CheckRun\",\"name\":\"Flate\",\"conclusion\":\"FAILURE\"}]" \
    "running-null|[{\"__typename\":\"CheckRun\",\"name\":\"Flate\",\"conclusion\":null}]" \
    "running-empty|[{\"__typename\":\"CheckRun\",\"name\":\"Flate\",\"conclusion\":\"\"}]" \
    "cancelled|[{\"__typename\":\"CheckRun\",\"name\":\"Flate\",\"conclusion\":\"CANCELLED\"}]" \
    "status-pending|[$flate_ok,{\"__typename\":\"StatusContext\",\"context\":\"x\",\"state\":\"PENDING\"}]" \
    "no-flate|[{\"__typename\":\"CheckRun\",\"name\":\"Other\",\"conclusion\":\"SUCCESS\"}]" \
    "flate-skipped|[{\"__typename\":\"CheckRun\",\"name\":\"Flate\",\"conclusion\":\"SKIPPED\"},{\"__typename\":\"CheckRun\",\"name\":\"Flate - Success\",\"conclusion\":\"SUCCESS\"}]" \
    "no-checks|[]"; do
    case_start "unfinished-${unfinished%%|*}"
    rollup=${unfinished#*|} pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
    touch "$FIX/on-main-$oid_a"
    echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
    status=$(run "$FIX/verdicts.json")
    assert "${unfinished%%|*} is commented, not merged" "logged 'a PR check is not finished or did not succeed' && ! logged 'gh pr merge'"
done

case_start skipped-check-allowed
rollup="[$flate_ok,{\"__typename\":\"CheckRun\",\"name\":\"Docs\",\"conclusion\":\"SKIPPED\"},{\"__typename\":\"CheckRun\",\"name\":\"Lint\",\"conclusion\":\"NEUTRAL\"}]" pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a skipped or neutral check beside a passed Flate still merges" "logged 'gh pr merge 69'"

case_start head-moved
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_b" OPEN
touch "$FIX/on-main-$oid_a"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a head that moved since the research is not merged" "! logged 'gh pr merge'"
assert "a moved head is reported" "grep -q '^#69 kener 4.1.8 -> 4.1.9: skipped, head moved' '$FIX/out'"

case_start no-domain
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
touch "$FIX/on-main-$oid_a"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
unset CLUSTER_DOMAIN
status=$(run "$FIX/verdicts.json")
assert "a missing CLUSTER_DOMAIN stops before any merge" "[[ $status != 0 ]] && ! logged 'gh pr merge' && ! logged 'gh pr comment'"

case_start bad-verdict
echo '[{"pr":69,"app":"kener","headRefOid":"x","verdict":"maybe"}]' >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "an unknown verdict is refused before gh runs" "[[ $status == 2 ]] && [[ ! -s '$LOG' ]]"

case_start dry-run
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN
pr_fixture 92 pegaprox 1.4.0 1.4.1 "$oid_b" OPEN
touch "$FIX/on-main-$oid_a" "$FIX/on-main-$oid_b"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe),$(verdict 92 pegaprox 1.4.0 1.4.1 "$oid_b" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json" --dry-run)
assert "dry run merges and comments nothing" "! logged 'gh pr merge' && ! logged 'gh pr comment' && ! logged 'git pull'"
assert "dry run names the action per PR" "grep -q '^#69 kener 4.1.8 -> 4.1.9: would merge' '$FIX/out' && grep -q '^#92 pegaprox 1.4.0 -> 1.4.1: would comment' '$FIX/out'"
assert "dry run exits 0" "[[ $status == 0 ]]"

case_start rerun
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" MERGED
pr_fixture 92 pegaprox 1.4.0 1.4.1 "$oid_b" OPEN
touch "$FIX/on-main-$oid_a" "$FIX/on-main-$oid_b"
sed -i.bak 's/"comments":\[\]/"comments":[{"body":"<!-- update-apps verdict -->\\nnever automerged"}]/' "$FIX/pr-92.json"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe),$(verdict 92 pegaprox 1.4.0 1.4.1 "$oid_b" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a rerun merges and comments nothing" "! logged 'gh pr merge' && ! logged 'gh pr comment' && ! logged 'git revert'"
assert "a rerun reports the earlier merge" "grep -q '^#69 kener 4.1.8 -> 4.1.9: merged earlier' '$FIX/out'"
assert "a rerun exits 0" "[[ $status == 0 ]]"

case_start reverted-earlier
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" MERGED
touch "$FIX/on-main-$oid_a"
echo "This reverts commit $merged." >"$FIX/reverts"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a merge reverted earlier is reported and left alone" "grep -q '^#69 kener 4.1.8 -> 4.1.9: reverted earlier' '$FIX/out' && ! logged 'git revert'"

case_start evidence-not-published
pr_fixture 96 radarr 6.4.4 7.0.0 "$oid_a" OPEN
verdict 96 radarr 6.4.4 7.0.0 "$oid_a" blocked | jq --arg e "major bump $fake_token" '[.evidence = $e]' >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a posted comment never carries the model's evidence" "logged 'gh pr comment 96' && ! logged '$fake_token' && logged \"see the run's research artifact\""

# research_ok <jq edit> applies the edit to a clean research output and runs the guard on it.
research_ok() {
    jq -n '{report: "ok", verdicts: [{app: "kener", namespace: "kener", headRefOid: ("a" * 40), from: "1.0.0", to: "1.0.1", bump: "patch", evidence: "notes"}]}' \
        | jq "$1" | jq -e -f "$here/research-guard.jq" >/dev/null
}
digest=sha256:$(printf 'a%.0s' {1..64})
case_start research-guard
assert "the guard passes a clean output" "research_ok ."
assert "the guard passes an empty verdict list" "research_ok '.verdicts = []'"
assert "the guard passes a not-ours verdict with no namespace" "research_ok '.verdicts[0].namespace = \"\"'"
assert "the guard passes a digest in the evidence" "research_ok '.verdicts[0].evidence = \"moved to $digest\"'"
assert "the guard refuses a GitHub token in the evidence" "! research_ok '.verdicts[0].evidence = \"x $fake_token\"'"
assert "the guard refuses a GitHub token in the report" "! research_ok '.report = \"x $fake_token\"'"
assert "the guard refuses an Anthropic token" "! research_ok '.report = \"x sk-ant-oat01-aaaaaaaaaaaaaaaaaaaaaaaa\"'"
assert "the guard refuses long evidence" "! research_ok '.verdicts[0].evidence = (\"x\" * 800)'"
for field in app namespace headRefOid from to bump; do
    assert "the guard refuses free text in $field" "! research_ok '.verdicts[0].$field = \"see https://evil.test\"'"
done

if [[ $fails -gt 0 ]]; then
    echo "$fails assertion(s) failed"
    exit 1
fi
echo "all cases passed"
