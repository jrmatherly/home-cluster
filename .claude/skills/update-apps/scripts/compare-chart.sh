#!/usr/bin/env bash
# Compare two versions of an app's chart, rendered with this cluster's values.
# Usage: compare-chart.sh <namespace> <app> <old-version> <new-version>
# Exits non-zero on bad usage, a failed chart pull, or a version that does not render.
# stderr says which.
set -euo pipefail

if [ $# -ne 4 ]; then
    echo "usage: compare-chart.sh <namespace> <app> <old-version> <new-version>" >&2
    exit 2
fi
ns=$1 app=$2 old=$3 new=$4

root=$(git rev-parse --show-toplevel)
dir="$root/kubernetes/apps/$ns/$app/app"
url=$(yq -r '.spec.url' "$dir/ocirepository.yaml")
out=$(mktemp -d)

yq '.spec.values // {}' "$dir/helmrelease.yaml" > "$out/values.yaml"
for version in "$old" "$new"; do
    helm show values "$url" --version "$version" > "$out/defaults-$version.yaml"
    helm template "$app" "$url" --version "$version" --namespace "$ns" \
        --values "$out/values.yaml" --include-crds > "$out/rendered-$version.yaml"
    yq -r '[.kind, .apiVersion, .metadata.namespace // "-", .metadata.name] | join(" ")' \
        "$out/rendered-$version.yaml" \
        | sort -u > "$out/resources-$version.txt"
done

diff -u "$out/defaults-$old.yaml" "$out/defaults-$new.yaml" > "$out/defaults.diff" || true
diff -u "$out/rendered-$old.yaml" "$out/rendered-$new.yaml" > "$out/rendered.diff" || true
diff -u "$out/resources-$old.txt" "$out/resources-$new.txt" > "$out/resources.diff" || true

# Changed lines without the two file headers. A YAML list item shows as "+- item",
# so the second character cannot be used to tell a change from a header.
changes() { grep -E '^[+-]' "$1" | grep -Ev '^(\+\+\+|---) ' || true; }
count() { grep -c . || true; }
# Every release changes the chart and version labels; they are not findings.
labels='helm.sh/chart|app.kubernetes.io/version|^[+-] *chart:'

echo "chart:              $url $old -> $new"
echo "default values:     $(changes "$out/defaults.diff" | count) changed lines   $out/defaults.diff"
echo "rendered manifests: $(changes "$out/rendered.diff" | grep -Ev "$labels" | count) changed lines besides version labels   $out/rendered.diff"
echo "resource set:       $(changes "$out/resources.diff" | count) added or removed   $out/resources.diff"
