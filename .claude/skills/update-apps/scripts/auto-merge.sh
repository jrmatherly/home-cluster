#!/usr/bin/env bash
# Merge the Renovate PRs that `/update-apps --auto` found safe, one at a time, and check each one
# against the live cluster. The research is text anyone upstream can write, so every verdict is
# re-checked here: the PR head must be the one researched, the diff must change version strings only,
# the app must be in references/auto-checks.yaml, and a head behind main is rendered with Flate first.
# A failed check reverts that merge and stops; a check that cannot run stops with no revert; every
# later app stays unmerged. Every other verdict gets one marked comment. Safe to rerun: a PR merged,
# reverted or commented earlier is reported and left alone.
#
# usage: auto-merge.sh verdicts.json [--dry-run]
# env:   CLUSTER_DOMAIN (the checks curl https://<host>.$CLUSTER_DOMAIN), GH_TOKEN for gh
# exit:  0 every merged app passed its checks, 1 a check failed or the run stopped, 2 bad input
set -Eeuo pipefail

marker='<!-- update-apps verdict -->'
here=$(cd "$(dirname "$0")" && pwd)
checks_file=$here/../references/auto-checks.yaml
apps_file=$here/../references/apps.md
timeout=20m
pr_fields=state,headRefOid,mergeCommit,statusCheckRollup,comments,author,isCrossRepository,headRefName

# Boundary: the arguments, the verdicts file and the tools, before anything touches gh.
verdicts=${1:-}
dry_run=false
[[ "${2:-}" == --dry-run ]] && dry_run=true
if [[ -z "$verdicts" || ! -f "$verdicts" || $# -gt 2 || ($# -eq 2 && $dry_run == false) ]]; then
    echo "usage: auto-merge.sh verdicts.json [--dry-run]" >&2
    exit 2
fi
if ! jq -e 'type == "array" and all(.[];
        (.pr | type == "number") and (.app | type == "string") and
        (.headRefOid | type == "string" and test("^[0-9a-f]{40}$")) and
        (.verdict | IN("safe", "needs template change", "blocked", "not ours")))' "$verdicts" >/dev/null; then
    echo "$verdicts: expected an array of {pr, app, headRefOid, verdict, ...} with a known verdict" >&2
    exit 2
fi
if [[ -z "${CLUSTER_DOMAIN:-}" ]]; then
    echo "CLUSTER_DOMAIN is unset, so no check can run" >&2
    exit 2
fi
for tool in gh git jq yq kubectl flux curl; do
    command -v "$tool" >/dev/null || { echo "$tool is not on PATH" >&2; exit 2; }
done
checks=$(yq -o=json "$checks_file")

tmp=$(mktemp -d "${TMPDIR:-/tmp}/auto-merge.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
stopped=""
outcome=""

# report <verdict json> <text>: one line per PR, the run's summary.
report() {
    echo "#$(jq -r '"\(.pr) \(.app) \(.from) -> \(.to)"' <<<"$1"): $2"
}

# comment <pr> <text>: one marked comment per PR, never a second. Needs pr-<n>.json fetched.
comment() {
    if jq -e --arg m "$marker" '.comments[].body | startswith($m)' "$tmp/pr-$1.json" >/dev/null 2>&1; then
        echo "commented earlier"
        return
    fi
    if $dry_run; then
        echo "would comment: $2"
        return
    fi
    gh pr comment "$1" --body "$marker"$'\n'"$2" >/dev/null
    echo "commented: $2"
}

# never_automerged <app>: apps.md marks the app's bullet `Tier 1: never`.
never_automerged() {
    awk -v app="$1" '/^- \*\*/ { p = ($0 ~ "^- \\*\\*" app "[ ,*(]") } p' "$apps_file" | grep -q 'Tier 1: never'
}

# renovate_pr <pr json>: a same-repository branch opened by the Renovate app. The repo is public,
# so anyone can open a PR, and a verdict alone must never be enough to merge one.
renovate_pr() {
    jq -e '.author.login == "app/renovate" and .isCrossRepository == false
        and (.headRefName | startswith("renovate/"))' "$1" >/dev/null
}

# version_only <diff> <namespace> <app>: every changed file is under the app's own directory in
# kubernetes/apps or template/config/kubernetes/apps, every changed line is a tag, version, image
# or reference value, and each pair differs in the version alone.
version_only() {
    local diff=$1 dir="apps/$2/$3/"
    grep -E '^(\+\+\+|---) ' "$diff" | grep -qvE "^(\+\+\+ b|--- a)/(kubernetes|template/config/kubernetes)/$dir" && return 1
    grep -E '^[-+]' "$diff" | grep -vE '^(\+\+\+|---) ' | grep -qvE '^[-+] *(- )?(tag|version|image|reference): \S+$' && return 1
    local key='s/^[-+]//; s/@sha256:[0-9a-f]{64}//; s/:[^:]*$//' removed added
    removed=$(grep -E '^-' "$diff" | grep -vE '^--- ' | sed -E "$key")
    added=$(grep -E '^\+' "$diff" | grep -vE '^\+\+\+ ' | sed -E "$key")
    [[ "$removed" == "$added" ]]
}

# flate_passes <pr> <namespace> <name>: render main with the PR applied and read the app's own line.
flate_passes() {
    local tree=$tmp/tree-$1 out
    git worktree add --detach "$tree" origin/main >/dev/null 2>&1
    git -C "$tree" apply "$tmp/pr-$1.diff"
    out=$(flate test all -p "$tree/kubernetes/flux/cluster" -n "$2" --no-progress \
        --cache-dir "${FLATE_CACHE_DIR:-$tmp/flate-cache}" --allow-missing-secrets 2>&1 || true)
    git worktree remove --force "$tree" >/dev/null 2>&1 || true
    grep -qE "✓ +(HelmRelease|Kustomization) +$2/$3\$" <<<"$out" && ! grep -qE "✗ .* $2/$3( |\$)" <<<"$out"
}

# app_checks <app json>: the Flux object, the cluster-wide readiness, then the app's own commands.
app_checks() {
    local ns kind name check
    ns=$(jq -r .namespace <<<"$1")
    kind=$(jq -r .kind <<<"$1")
    name=$(jq -r .name <<<"$1")
    sleep "$(jq -r .wait <<<"$1")"
    case "$kind" in
        HelmRelease) kubectl -n "$ns" wait "helmrelease/$name" --for=condition=Ready --timeout=$timeout ;;
        Deployment) kubectl -n "$ns" rollout status "deploy/$name" --timeout=$timeout ;;
        StatefulSet) kubectl -n "$ns" rollout status "sts/$name" --timeout=$timeout ;;
        *) echo "unknown kind $kind in auto-checks.yaml" >&2; return 1 ;;
    esac
    [[ $(flux get hr -A --status-selector ready=false | wc -l) -le 1 ]]
    [[ $(flux get ks -A --status-selector ready=false | wc -l) -le 1 ]]
    while IFS= read -r check; do
        [[ -n "$check" ]] || continue
        echo "  check: $check"
        bash -c "$check" || return 1
    done < <(jq -r '.checks[]' <<<"$1")
}

# merge_app <verdict json> <app json>: the whole path for one safe, listed PR. Sets outcome, and
# stopped when a check failed. Any other failing command stops the run through the ERR trap.
merge_app() {
    local v=$1 app=$2 pr head ns name merge_commit
    pr=$(jq -r .pr <<<"$v")
    head=$(jq -r .headRefOid <<<"$v")
    ns=$(jq -r .namespace <<<"$app")
    name=$(jq -r .name <<<"$app")
    gh pr view "$pr" --json "$pr_fields" >"$tmp/pr-$pr.json"
    merge_commit=$(jq -r '.mergeCommit.oid // ""' "$tmp/pr-$pr.json")
    case "$(jq -r .state "$tmp/pr-$pr.json")" in
        MERGED)
            if git log origin/main --grep="This reverts commit $merge_commit" | grep -q .; then
                outcome="reverted earlier"
            else
                outcome="merged earlier, not re-checked"
            fi
            return
            ;;
        OPEN) ;;
        *) outcome="skipped, PR is $(jq -r .state "$tmp/pr-$pr.json")"; return ;;
    esac
    if [[ "$(jq -r .headRefOid "$tmp/pr-$pr.json")" != "$head" ]]; then
        outcome="skipped, head moved since the research"
        return
    fi
    if ! renovate_pr "$tmp/pr-$pr.json"; then
        outcome=$(comment "$pr" "safe by research, but not a same-repository Renovate PR, so not merged")
        return
    fi
    if jq -e '[.statusCheckRollup[] | select(.conclusion == "FAILURE")] | length > 0' "$tmp/pr-$pr.json" >/dev/null; then
        outcome=$(comment "$pr" "safe by research, but a PR check failed, so not merged")
        return
    fi
    gh pr diff "$pr" >"$tmp/pr-$pr.diff"
    if ! version_only "$tmp/pr-$pr.diff" "$ns" "$(jq -r --arg a "$(jq -r .app <<<"$v")" '.dir // $a' <<<"$app")" >/dev/null; then
        outcome=$(comment "$pr" "safe by research, but the diff changes more than version strings under the app's own directory, so not merged")
        return
    fi
    git fetch origin "refs/pull/$pr/head" >/dev/null 2>&1
    if ! git merge-base --is-ancestor origin/main "$head" && ! flate_passes "$pr" "$ns" "$name"; then
        outcome=$(comment "$pr" "safe by research, but Flate fails on main with this PR applied, so not merged")
        return
    fi
    if $dry_run; then
        outcome="would merge"
        return
    fi
    if [[ "$(git rev-parse origin/main)" != "$(git rev-parse HEAD)" ]]; then
        stopped="origin/main moved under the run"
        outcome="not merged, $stopped"
        return
    fi
    gh pr merge "$pr" --rebase --delete-branch --match-head-commit "$head"
    git pull --ff-only
    gh pr view "$pr" --json "$pr_fields" >"$tmp/pr-$pr.json"
    merge_commit=$(jq -r '.mergeCommit.oid' "$tmp/pr-$pr.json")
    # The push reaches Flux through the flux-webhook Receiver, or its one-minute poll; the runner
    # has no write on Flux objects, so nothing nudges it.
    kubectl -n flux-system wait kustomization/flux-system \
        "--for=jsonpath={.status.lastAppliedRevision}=refs/heads/main@sha1:$merge_commit" --timeout=10m
    if app_checks "$app" >&2; then
        outcome="merged, checks passed"
        return
    fi
    stopped="a check failed, merge $merge_commit reverted"
    git -c user.name=update-apps -c user.email=update-apps@users.noreply.github.com revert --no-edit "$merge_commit"
    git push origin HEAD:main
    comment "$pr" "merged as $merge_commit, a post-deploy check failed, reverted. Run the checks in references/auto-checks.yaml by hand before merging again." >/dev/null
    outcome="merged, a check failed, reverted"
}

current="the setup"
trap 'echo "Stopped on: $current, a command failed, nothing reverted"; exit 1' ERR
git fetch -q origin main
$dry_run || git pull -q --ff-only

# Safe verdicts for listed apps go first, in the registry's order; everything else gets a comment.
handled=()
while IFS= read -r app_name; do
    v=$(jq -c --arg a "$app_name" '.[] | select(.app == $a and .verdict == "safe")' "$verdicts" | head -n 1)
    [[ -n "$v" ]] || continue
    pr=$(jq -r .pr <<<"$v")
    handled+=("$pr")
    current=$(jq -r '"#\(.pr) \(.app)"' <<<"$v")
    if never_automerged "$app_name"; then
        gh pr view "$pr" --json "$pr_fields" >"$tmp/pr-$pr.json"
        report "$v" "$(comment "$pr" "safe by research, but apps.md marks $app_name never automerged, so merged by hand only")"
        continue
    fi
    if [[ -n "$stopped" ]]; then
        report "$v" "not merged, the run stopped earlier"
        continue
    fi
    merge_app "$v" "$(jq -c --arg a "$app_name" '.apps[$a]' <<<"$checks")"
    report "$v" "$outcome"
    [[ -z "$stopped" ]] || stop_on=$current
done < <(jq -r '.apps | keys_unsorted[]' <<<"$checks")

while IFS= read -r v; do
    pr=$(jq -r .pr <<<"$v")
    current=$(jq -r '"#\(.pr) \(.app)"' <<<"$v")
    printf '%s\n' "${handled[@]:-}" | grep -qx "$pr" && continue
    verdict=$(jq -r .verdict <<<"$v")
    if [[ "$verdict" == safe ]] && never_automerged "$(jq -r .app <<<"$v")"; then
        text="safe by research, but apps.md marks $(jq -r .app <<<"$v") never automerged, so merged by hand only"
    elif [[ "$verdict" == safe ]]; then
        text="safe by research, but $(jq -r .app <<<"$v") has no scripted check in references/auto-checks.yaml, so merged by hand only"
    else
        text="$verdict. $(jq -r .evidence <<<"$v")"
    fi
    gh pr view "$pr" --json "$pr_fields" >"$tmp/pr-$pr.json"
    if [[ "$(jq -r .state "$tmp/pr-$pr.json")" != OPEN ]]; then
        report "$v" "skipped, PR is $(jq -r .state "$tmp/pr-$pr.json")"
        continue
    fi
    report "$v" "$(comment "$pr" "$text")"
done < <(jq -c '.[]' "$verdicts")

if [[ -n "$stopped" ]]; then
    echo "Stopped on: ${stop_on:-$current}, $stopped"
    exit 1
fi
