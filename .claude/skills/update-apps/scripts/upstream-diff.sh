#!/usr/bin/env bash
# Diff two refs of an upstream GitHub repository, for the research step.
# Usage: upstream-diff.sh <owner/repo> <from-ref> <to-ref> [path ...]
# Prints the --stat summary, then the full diff of the given paths (or of everything).
# The clone goes under TMPDIR with a shallow history, and git runs with no external diff,
# no pager and no user or system config, so a cloned repository cannot run anything here.
# Exits non-zero on bad usage or when a ref does not exist. stderr says which.
set -euo pipefail

if [ $# -lt 3 ] || ! [[ "$1" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] \
    || [[ "$2" == -* || "$3" == -* ]]; then
    echo "usage: upstream-diff.sh <owner/repo> <from-ref> <to-ref> [path ...]" >&2
    exit 2
fi
repo=$1 from=$2 to=$3
shift 3

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_PAGER=cat \
    GIT_TERMINAL_PROMPT=0 GIT_EXTERNAL_DIFF='' GIT_DIFF_OPTS=''
out=$(mktemp -d "${TMPDIR:-/tmp}/upstream-diff.XXXXXX")
trap 'rm -rf "$out"' EXIT
git init -q "$out"
git -C "$out" remote add origin "https://github.com/$repo.git"
for ref in "$from" "$to"; do
    git -C "$out" fetch -q --depth 1 origin "$ref" \
        || { echo "upstream-diff.sh: $repo has no ref $ref" >&2; exit 1; }
    git -C "$out" tag -f "upstream-diff/$ref" FETCH_HEAD
done
git -C "$out" diff --no-ext-diff --no-color --stat=120 "upstream-diff/$from" "upstream-diff/$to" -- "$@"
echo
git -C "$out" diff --no-ext-diff --no-color "upstream-diff/$from" "upstream-diff/$to" -- "$@"
