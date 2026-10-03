# Conventions

- Editorconfig: 2-space indent, LF, final newline; Markdown 4-space; shell 4-space.
- YAML/JSON/Markdown formatted by oxfmt (width 100); rendered output must already be oxfmt-clean (CI runs `oxfmt --check` on rendered dirs), so templates must render formatted YAML.
- Templates: makejinja delimiters `#{ }#` / `#% %#`; config keys referenced as nested objects from validated cluster.toml (e.g. `kubernetes.api.addr`, `nodes[].name`). Pin versions with `# renovate: datasource=… depName=…` comments.
- Talos patches: numbered files under `talos/all/` (00 install … 71 filesystem); `.tpl` suffix = per-node topf Go template.
- Python (template/scripts): single-quoted strings in plugin.py; pydantic `Model` base + `Annotated` validators in validate.py; errors surfaced via `ConfigError`/`format_errors` one per line. Tests import from `validate` with sys.path insert.
- Config schema changes: update validate.py, `cluster.sample.toml` docs, regenerate schema, add valid/invalid fixtures.
- just recipes: `[doc()]` + `[group()]` attributes, `[private]` helpers, bash `-euo pipefail`, log via `just log <lvl> "<msg>" key val`.
