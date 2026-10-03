# Suggested commands

Run from repo root; tools come from `mise install`.

- `just init` — create cluster.toml (from sample), age.key, deploy.key, webhook token if missing.
- `just configure` — render (makejinja) → sops-encrypt `*.sops.*` → kubeconform → topf render check.
- `just template doctor` — prerequisite files + schema check.
- `just template schema` — regenerate `cluster.schema.json` from validate.py.
- `just template test-helmfile` — render bootstrap charts (network needed).
- `just template reset` — delete rendered bootstrap/ kubernetes/ talos/ .sops.yaml (confirm prompt).
- `uv run --locked --no-dev template/scripts/validate.py cluster.toml` — validate a config/fixture, print JSON.
- `uv run --locked pytest template/scripts/test_validate.py -q` — validator unit tests.
- `taplo check --schema "file://$PWD/cluster.schema.json" ./cluster.toml`
- After render: `just bootstrap talos|apps`, `just talos render|apply-node <n>|upgrade-node <n>`, `just kube …`.
- Darwin: BSD sed/find; use `sd` (installed) for regex replace instead of `sed -i`.
