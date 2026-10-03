# Task completion

Template, validator and fixture changes are checked automatically by the Stop hook (`.claude/hooks/stop.py`, wired in `.claude/settings.json`): it renders every valid fixture and runs oxfmt, kubeconform, topf, and pytest when scripts changed, blocking until green.
Run manually: `zizmor --offline .github/workflows/*.yaml` for workflow edits; `mise lock` after mise config edits (lefthook also does this on commit).
See the "Best Practices" section of `CLAUDE.md`.
