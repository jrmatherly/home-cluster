---
paths:
    - ".claude/skills/cluster-guard/**"
---

# cluster-guard internals

The summary of what the mod refuses is in `CLAUDE.md` under Best Practices. This file holds how it decides.

- Since 2026-11-01 one shell tokenizer reads every Bash command: quotes are resolved, comments dropped, and nested shells, `eval`, command substitutions and an unquoted heredoc's body count as commands. A quoted heredoc (`<<'EOF'`) is data only when every command on its line passes `storesText()` (`cat`, `tee`, `gh`, `git commit`), so `cat > "$TMPDIR/x.sh" <<'EOF'` may mention a secret, while `cat <<'EOF' | bash`, `php <<'EOF'` and `git add . && cat > x <<'EOF'` parse the body: an allowlist of sinks, because a list of interpreters misses one (a review found php, lua and npx). `command()` and `isReader()` look past `VAR=value` and an `rtk` prefix with `bypass` or flags, so the rtk hook's rewrite keeps a `grep` pattern and the allowed readers exempt.
- A rendered path counts as a write only where the command writes it: a redirect target, `>|` and `&>` included, a file given to `tee`, the destination of `cp`, `install` or `rsync`, `cp -t`, either end of `mv`, a file given to `sd`, `sed -i`, `perl -pi`, `yq -i`/`--inplace` or `sops -i`/`--in-place`, or any of those through `find -exec` or `xargs`, in relative, `./`, `$PWD`, absolute or quoted form, so reading one into scratch is allowed. The mod's tests run from lefthook whenever its files are staged.
- A secret file name counts whether it is quoted, globbed, braced or spliced. Only a `git commit` message and a `grep` or `rg` pattern count as text, so `echo "<name>"` is refused too (measured live 2026-11-02). A long flag's own name (`--kubeconfig`) is stripped before matching, its value is not.
- `talos/rendered/` is a secret path (`SECRET_DIR`): `just talos render` writes full machine configs there, about nine key, token, secret or certificate fields per control plane. A glob counts when the whole word or any directory part of it could match `talos/rendered`, so `talos/*/*.yaml` is refused.
- Node maintenance covers the `just talos` drain, apply, apply-node, upgrade-node, upgrade-k8s, reset-node, stop-node and reboot-node recipes, through `just`'s flags or `talos::` too, and the all-node `upgrade` and `reset`, plus raw `talosctl upgrade`, `upgrade-k8s`, `reset`, `apply-config`, `reboot` or `shutdown`, `topf apply`, `upgrade` or `reset`, and `kubectl drain` (`NODE_OPS`; `talosctl version` and `topf render` pass). The 1Password guard refuses `op read`, `inject`, `run`, `item get` and `document get` at any hour.
- Known limits: paths reaching `xargs` on stdin, a shell run by `find -exec`, an `env` or `sudo` prefix on an in-place editor, a reader's output redirected to a file, `rendered/...` named from inside `talos/` after a `cd`, and a script written from a quoted heredoc and run on a later line.
- The gitignored `.claude/skills/cluster-guard/.claude-plugin/types/` is where Claude Code lays type declarations for a mod it hot-reloads; `/reload-plugins` did not lay it, and a plugin folder added while a session is open loads only after that session restarts or runs `/reload-plugins` (both measured 2026-10-10).
