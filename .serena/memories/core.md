# home-cluster — core

Fork of onedr0p/cluster-template (origin jrmatherly/home-cluster). Talos + Kubernetes + Flux home cluster rendered from a single `cluster.toml` via makejinja. The cluster is bootstrapped and live: Flux reconciles `kubernetes/` from Git, so a change is `.j2` edit → `just configure` → commit → push.

## Source map

- `template/config/**` — Jinja sources (`*.j2`), rendered to the repo root (makejinja `output = "./"`). The rendered `bootstrap/`, `kubernetes/`, `talos/` and `.sops.yaml` are committed; edit the `.j2` source, never the rendered copy (the `cluster-guard` mod refuses such writes).
    - `kubernetes/apps/<namespace>/<app>/`, `kubernetes/components/{sops,postgres,redis}`, `kubernetes/flux/cluster`.
    - `talos/all/*.yaml[.tpl].j2` (numbered patches for all nodes), `talos/control-plane/`, `talos/topf.yaml.j2` (topf node inventory).
    - `bootstrap/helmfile/*.yaml.j2`, sops-encrypted secrets `*.sops.yaml.j2`.
    - `*/mod.just` — become `just bootstrap|kube|talos` modules after render (optional `mod?` in root justfile).
- `template/overrides/` — second makejinja input; `*.partial.yaml.j2` excluded from output.
- `template/scripts/validate.py` — pydantic schema for `cluster.toml` (defaults, cross-field checks); `plugin.py` — makejinja `Plugin` (data = validated config + secrets/key helpers); `check_layout.py` — section order vs the sample; `test_validate.py` — pytest.
- `template/mod.just` — `just template …` recipes (configure/doctor/init/schema/check-layout/reset/tidy/test-helmfile).
- `cluster.sample.toml` (documented config, layout of record) → `just init` copies to the gitignored config; `cluster.schema.json` generated from validate.py.
- `.github/template-tests/{valid,invalid,e2e}` — fixtures; `.github/workflows/` — template CI (gated to `onedr0p/cluster-template`, skips on this fork), plus model-images, docs-image, label sync.
- `images/<model>/Dockerfile` — model image recipes (GGUF in a scratch image) that `ai/localai` mounts as image volumes.
- `docs/` — public Nimbus (Astro) docs site; pages are scrubbed copies of the gitignored `private/` guides.
- Apps and their `cluster.toml` sections: the "Detected Patterns" section of `CLAUDE.md` is the one list; do not copy it here.

## Invariants

- makejinja delimiters are custom: `#{ var }#`, `#% block %#`, `#| comment #|`. Plain `{{ }}` passes through untouched — used for topf Go templates in `*.tpl.j2` (e.g. `{{ .Node.Host }}`) and Helm/Flux syntax.
- `undefined = "strict"`: any missing var fails render.
- A schema change touches validate.py, the sample, `cluster.schema.json` (`just template schema`; tests fail on drift) and the fixtures; a new invalid fixture also goes into the `validate-invalid` matrix in `template-e2e.yaml` (`.claude/rules/validator.md`).
- The key files, kubeconfig, talosconfig and the config are gitignored (`.gitignore`); never print the config, read it through the validator. `*.sops.*` files are re-encrypted by every `just configure`; restore the unchanged ones before committing (`CLAUDE.md` Detected Patterns, last bullet).
- `just template tidy` is one-way: archives all template tooling to `.private/<ts>/`.

Claude Code setup: `.claude/settings.json` (secret-file Read denies, ask rules for destructive commands, Stop hook `.claude/hooks/stop.py`), `.claude/rules/` (path-scoped conventions), `.claude/skills/cluster-guard/` (hooks mod: refuses writes into rendered trees and prints of secret files, blocks node maintenance in the UniFi auto-update window), `.claude/skills/update-apps/` (chart and image bumps).

See `mem:tech_stack` (tools, operators, formatters), `mem:suggested_commands` (where the commands are listed), `mem:conventions` (where the conventions are), `mem:task_completion` (what runs before a turn or commit may end).
