# home-cluster — core

Fork of onedr0p/cluster-template (origin jrmatherly/home-cluster). Talos + Kubernetes + Flux home cluster generated from a single `cluster.toml` via makejinja.

## Source map

- `template/config/**` — Jinja sources (`*.j2`), rendered to repo root (makejinja `output = "./"`). Generated dirs `bootstrap/`, `kubernetes/`, `talos/`, `.sops.yaml` do NOT exist until `just configure`; edit the `.j2` source, never the rendered copy.
    - `kubernetes/apps/<namespace>/<app>/`, `kubernetes/components/sops`, `kubernetes/flux/cluster`.
    - `talos/all/*.yaml[.tpl].j2` (numbered patches for all nodes), `talos/control-plane/`, `talos/topf.yaml.j2` (topf node inventory).
    - `bootstrap/helmfile/*.yaml.j2`, sops-encrypted secrets `*.sops.yaml.j2`.
    - `*/mod.just` — become `just bootstrap|kube|talos` modules after render (optional `mod?` in root justfile).
- `template/overrides/` — second makejinja input; `*.partial.yaml.j2` excluded from output.
- `template/scripts/validate.py` — pydantic schema for `cluster.toml` (defaults, cross-field checks); `plugin.py` — makejinja `Plugin` (data = validated config + secrets/key helpers); `test_validate.py` — pytest.
- `template/mod.just` — `just template …` recipes (configure/doctor/init/schema/reset/tidy/test-helmfile).
- `cluster.sample.toml` (documented config) → `just init` copies to gitignored `cluster.toml`; `cluster.schema.json` generated from validate.py.
- `.github/template-tests/{valid,invalid,e2e}` — fixtures; `.github/workflows/template-*.yaml` CI (jobs gated to `github.repository == 'onedr0p/cluster-template'`, so they skip on this fork).

## Invariants

- makejinja delimiters are custom: `#{ var }#`, `#% block %#`, `#| comment #|`. Plain `{{ }}` passes through untouched — used for topf Go templates in `*.tpl.j2` (e.g. `{{ .Node.Host }}`) and Helm/Flux syntax.
- `undefined = "strict"`: any missing var fails render.
- Changing the pydantic model requires regenerating `cluster.schema.json` (`just template schema`); tests fail on drift.
- New invalid fixture → also add it to the `validate-invalid` matrix in `template-e2e.yaml`.
- Secrets (age.key, deploy.key, flux-webhook-token.txt, cloudflare-tunnel.json, kubeconfig, talosconfig, cluster.toml) are gitignored; never commit them. `*.sops.*` files get encrypted in place by `just configure`.
- `just template tidy` is one-way: archives all template tooling to `.private/<ts>/`.

Claude Code setup: `.claude/settings.json` (secret-file Read denies, ask rules for destructive commands, Stop hook `.claude/hooks/stop.py`), `.claude/rules/` (path-scoped conventions).

See `mem:tech_stack` (tools/versions), `mem:suggested_commands` (just/uv/mise commands), `mem:conventions` (formatting + template style), `mem:task_completion` (checks before done).
