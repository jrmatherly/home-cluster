#!/usr/bin/env bash
# Prints flate's --supply document: supply.yaml plus a placeholder cluster-secrets
# for every namespace under kubernetes/apps. The ClusterExternalSecret writes those
# copies only in the cluster, so without them every Kustomization is blocked.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
cat "$root/.github/flate/supply.yaml"
for dir in "$root"/kubernetes/apps/*/; do
  printf -- '---\napiVersion: v1\nkind: Secret\nmetadata:\n  name: cluster-secrets\n  namespace: %s\nstringData:\n  SECRET_DOMAIN: example.com\n' "$(basename "$dir")"
done
