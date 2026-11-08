#!/usr/bin/env bash
# Renders one fixture in a scratch copy of the tracked files, as .claude/hooks/stop.py
# does, so the worktree's rendered trees are never touched. Prints the scratch path.
set -euo pipefail
trap 'echo "render-check: failed at line $LINENO" >&2' ERR

# Run from the repository root.
fixture=$(realpath "$1")
repo=$PWD
scratch=$(mktemp -d "${TMPDIR:-/tmp}/career-ops-render.XXXXXX")

git ls-files --cached --others --exclude-standard > "$scratch/.files"
while IFS= read -r f; do
    # Skips files deleted from the working tree but still in the index.
    [ -f "$repo/$f" ] || continue
    mkdir -p "$scratch/$(dirname "$f")"
    cp -p "$repo/$f" "$scratch/$f"
done < "$scratch/.files"
rm "$scratch/.files"

# The repo's tool paths, so mise's shims never resolve against the untrusted scratch config.
eval "$(mise env -s bash)"
cd "$scratch"
age-keygen -o age.key
ssh-keygen -q -t ed25519 -N "" -f deploy.key
printf '%032d\n' 0 > flux-webhook-token.txt
printf '%s' '{"AccountTag":"fake","TunnelSecret":"fake","TunnelID":"fake"}' > cloudflare-tunnel.json
rm -rf bootstrap kubernetes talos .sops.yaml
cp "$fixture" cluster.toml

export UV_PROJECT_ENVIRONMENT="$repo/.venv" SOPS_AGE_KEY_FILE="$scratch/age.key" SOPS_CONFIG="$scratch/.sops.yaml" \
    KUBECONFIG="$scratch/kubeconfig" TALOSCONFIG="$scratch/talos/talosconfig"
uv run --quiet --locked --no-dev makejinja
oxfmt --check ./.sops.yaml ./bootstrap ./kubernetes ./talos
echo "rendered: $scratch"
# Needs network for the schemas.
bash template/resources/kubeconform.sh kubernetes
