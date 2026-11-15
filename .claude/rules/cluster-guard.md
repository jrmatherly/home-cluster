---
paths:
    - ".claude/skills/cluster-guard/**"
---

# cluster-guard internals

The summary of what the mod refuses is in `CLAUDE.md` under Best Practices. This file holds how it decides.

- Since 2026-11-01 one shell tokenizer reads every Bash command: quotes are resolved, comments dropped, and nested shells, `eval`, command substitutions and a heredoc fed to anything but `gh` or `git commit` count as commands.
- A rendered path counts as a write only where the command writes it: a redirect target, `>|` and `&>` included, a file given to `tee`, the destination of `cp`, `install` or `rsync`, `cp -t`, either end of `mv`, a file given to `sd`, `sed -i`, `perl -pi`, `yq -i`/`--inplace` or `sops -i`/`--in-place`, or any of those through `find -exec` or `xargs`, the root `.sops.yaml` included, in relative, `./`, `$PWD`, absolute or quoted form, so reading one into scratch is allowed. The mod's tests run from lefthook whenever its files are staged.
- A secret file name counts whether it is quoted, globbed, braced or spliced. Only a `git commit` message and a `grep` or `rg` pattern count as text, so `echo "<name>"` is refused too (measured live 2026-11-02).
- Node maintenance covers the `just talos` drain, apply, apply-node, upgrade-node, upgrade-k8s, reset-node, stop-node and reboot-node recipes, through `just`'s flags or `talos::` too, and the all-node `upgrade` and `reset`, plus raw `talosctl`, `topf` and `kubectl drain`.
- Known limits: paths reaching `xargs` on stdin, a shell run by `find -exec`, an `env` or `sudo` prefix on an in-place editor, and a reader's output redirected to a file.
- The gitignored `.claude/skills/cluster-guard/.claude-plugin/types/` is where Claude Code lays type declarations for a mod it hot-reloads; `/reload-plugins` did not lay it, and a plugin folder added while a session is open loads only after that session restarts or runs `/reload-plugins` (both measured 2026-10-10).
