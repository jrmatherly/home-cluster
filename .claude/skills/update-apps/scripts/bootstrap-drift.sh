#!/usr/bin/env bash
# Show live fields the bootstrap `helm` field manager still owns that the current
# Helm release manifest no longer carries, for every chart `just bootstrap apps`
# installed. helm-controller applies server-side and cannot prune a field another
# manager owns, so a key a chart drops stays live until the `helm` manager lets
# go of it (cilium-config kept envoy-xds-mode: ads after 1.20.4, 2026-10-24).
#
# usage: bootstrap-drift.sh           dry diff only (read-only)
#        bootstrap-drift.sh --apply   re-apply each manifest as the `helm` manager,
#                                     which releases the stale fields; Deployments
#                                     and DaemonSets whose pod template changes roll
set -euo pipefail

releases=(kube-system/cilium kube-system/coredns kube-system/spegel cert-manager/cert-manager
    flux-system/flux-operator flux-system/flux-instance)
mode=${1:-}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

for release in "${releases[@]}"; do
    ns=${release%/*}
    name=${release#*/}
    manifest="$tmp/$name.yaml"
    if ! helm -n "$ns" get manifest "$name" >"$manifest" 2>/dev/null; then
        echo "== $release: no Helm release found (needs the release Secrets, so not a runner job)" >&2
        exit 1
    fi
    echo "== $release"
    # A release manifest may hold objects in another namespace (cilium-secrets, cert-manager's
    # kube-system roles), which kubectl refuses next to -n, so documents that name their
    # namespace go without -n and the rest take the release namespace.
    yq 'select(.metadata.namespace != null)' "$manifest" >"$tmp/$name.named.yaml"
    yq 'select(.metadata.namespace == null)' "$manifest" >"$tmp/$name.unnamed.yaml"
    for part in named unnamed; do
        file="$tmp/$name.$part.yaml"
        [[ -s "$file" ]] || continue
        flags=(--server-side --field-manager=helm --force-conflicts -f "$file")
        [[ "$part" == unnamed ]] && flags=(-n "$ns" "${flags[@]}")
        # kubectl diff exits 1 when there is a difference, which is the finding, not a failure.
        kubectl diff "${flags[@]}" | grep -E '^[-+][^-+]' | grep -vE 'resourceVersion|generation' || true
        if [[ "$mode" == "--apply" ]]; then
            kubectl apply "${flags[@]}" >/dev/null
        fi
    done
    if [[ "$mode" == "--apply" ]]; then
        echo "   applied as the helm manager"
    fi
done
