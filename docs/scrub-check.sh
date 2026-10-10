#!/usr/bin/env bash
# Refuses docs pages that carry operator details. The site is public, so a
# page may describe the cluster only in placeholders: no private addresses,
# MAC addresses, email addresses or long tokens, and nothing in the denylist
# (one fixed string per line, matched case-insensitively, kept out of Git).
# Prints file:line and the rule, never the matched text, so a CI log cannot
# leak what the page did.
#
#   docs/scrub-check.sh [file...]            default: every file under docs/src/content
#   SCRUB_DENYLIST=path docs/scrub-check.sh  default: private/scrub-denylist.txt
#
# A denylist named in the environment must exist and have an entry: the image
# build names it, so a build that lost its secret fails instead of passing.
set -euo pipefail

cd "$(dirname "$0")/.."
denylist="${SCRUB_DENYLIST:-private/scrub-denylist.txt}"

files=()
for f in "$@"; do [ -f "$f" ] && files+=("$f"); done
if [ "$#" -eq 0 ]; then
    while IFS= read -r f; do files+=("$f"); done < <(find docs/src/content -type f | sort)
fi
[ "${#files[@]}" -gt 0 ] || exit 0

patterns=$(grep -v '^[[:space:]]*$' "$denylist" 2>/dev/null || true)
if [ -z "$patterns" ]; then
    if [ -n "${SCRUB_DENYLIST:-}" ]; then
        echo "scrub-check: SCRUB_DENYLIST=$SCRUB_DENYLIST is missing or empty" >&2
        exit 2
    fi
    echo "scrub-check: no denylist at $denylist, checking the regex rules only" >&2
fi

# Each rule is a name, a regex, and a filter that drops matches which only
# look like a token: image digests and checksums (all hex), table rules (all
# dashes), and git's SSH user in a remote URL.
names=(rfc1918-address mac-address email-address long-token)
regexes=(
    '\b(10\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])|192\.168)\.[0-9]{1,3}\.[0-9]{1,3}\b'
    '\b([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b'
    '[[:alnum:]._%+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}'
    '[A-Za-z0-9_-]{40,}'
)
excludes=('^$' '^$' '^git@' '^([0-9a-fA-F]+|[-_]+)$')

# Reads grep's file:line:match lines, drops matches the filter excludes, and
# prints each file:line once with the rule name.
report() {
    local rule="$1" exclude="$2"
    awk -F: -v rule="$rule" -v exclude="$exclude" '
        { match_text = substr($0, length($1) + length($2) + 3) }
        match_text ~ exclude { next }
        !seen[$1 ":" $2]++ { print $1 ":" $2 ": " rule }'
}
# grep exits 1 for no match, the good case; anything else is a failure.
scan() {
    local rule="$1"; shift
    grep -n -H -o "$@" "${files[@]}" || [ $? -eq 1 ] || {
        echo "scrub-check: grep failed on the $rule rule" >&2
        exit 2
    }
}

found=""
for i in "${!names[@]}"; do
    hits=$(scan "${names[$i]}" -E "${regexes[$i]}" | report "${names[$i]}" "${excludes[$i]}") || exit 2
    [ -z "$hits" ] || found+="$hits"$'\n'
done
if [ -n "$patterns" ]; then
    hits=$(scan denylist -F -i -f <(printf '%s\n' "$patterns") | report denylist '^$') || exit 2
    [ -z "$hits" ] || found+="$hits"$'\n'
fi

if [ -n "$found" ]; then
    printf '%s' "$found"
    echo "scrub-check: operator details found; replace them with placeholders" >&2
    exit 1
fi
