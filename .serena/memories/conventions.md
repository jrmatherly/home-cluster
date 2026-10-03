# Conventions

Source of truth is outside Serena, to avoid drift:

- `CLAUDE.md` (always loaded): global conventions, formatting, just recipe style.
- `.claude/rules/*.md` (path-scoped): `templates.md` (makejinja), `talos.md` (topf/Talos patches), `flux-apps.md` (Flux app layout), `validator.md` (cluster.toml schema changes).
  Read the matching rule file before editing in that area.
