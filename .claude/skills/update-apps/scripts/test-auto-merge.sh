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
[[ "$1" == get ]] && echo "NAMESPACE NAME REVISION SUSPENDED READY MESSAGE"
exit 0
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

# pr_fixture <pr> <app> <from> <to> <oid> <state> [failed-check] writes pr-N.json and a version-only diff.
pr_fixture() {
    local pr=$1 app=$2 from=$3 to=$4 oid=$5 state=$6 check=${7:-SUCCESS}
    cat >"$FIX/pr-$pr.json" <<EOF
{"state":"$state","headRefOid":"$oid","mergeCommit":{"oid":"$merged"},
 "statusCheckRollup":[{"name":"Flate","conclusion":"$check"},{"name":null,"conclusion":null}],
 "comments":[]}
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
assert "safe listed app reconciles the source" "logged 'flux reconcile source git flux-system'"
assert "safe listed app exits 0" "[[ $status == 0 ]]"
assert "safe listed app reports merged and passed" "grep -q '^#69 kener 4.1.8 -> 4.1.9: merged, checks passed' '$FIX/out'"
assert "safe listed app does not run flate when the head is on main" "! logged 'flate '"

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

case_start failed-flate-check
pr_fixture 69 kener 4.1.8 4.1.9 "$oid_a" OPEN FAILURE
touch "$FIX/on-main-$oid_a"
echo "[$(verdict 69 kener 4.1.8 4.1.9 "$oid_a" safe)]" >"$FIX/verdicts.json"
status=$(run "$FIX/verdicts.json")
assert "a PR with a failed check is commented, not merged" "logged 'gh pr comment 69' && ! logged 'gh pr merge'"

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

if [[ $fails -gt 0 ]]; then
    echo "$fails assertion(s) failed"
    exit 1
fi
echo "all cases passed"
