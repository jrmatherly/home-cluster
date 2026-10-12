# Task completion

- Stop hook (`.claude/hooks/stop.py`, wired in `.claude/settings.json`): runs when anything under `template/`, `cluster.sample.toml`, `cluster.schema.json`, `makejinja.toml`, `pyproject.toml`, `uv.lock` or `.github/template-tests/` differs from `main`. In a scratch copy it always runs pytest and `oxfmt --check .`, renders every valid fixture and oxfmt-checks the output, and runs kubeconform and topf on the `public` fixture only (kubeconform is skipped offline). It blocks the turn on a failure, lets the turn end on a second Stop with the same unchanged failure, and fails open on its own errors.
- Commit hooks (`.lefthook.toml`): oxfmt, `just --fmt`, `mise fmt`, `mise lock`, zizmor on staged workflows, ruff, shellcheck, markdownlint, `docs/scrub-check.sh` on staged docs pages, `claude plugin test` on cluster-guard when its files are staged.
- Run by hand: `zizmor --offline .github/workflows/*.yaml` for workflow edits before the commit; `mise lock` after a mise config edit, then commit `.mise/mise.lock`.
  See the "Best Practices" section of `CLAUDE.md`.
