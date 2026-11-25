# cluster-guard

A Claude Code hooks module for this repo. It refuses three things before the tool runs:

- **Rendered files.** An Edit or Write under `bootstrap/`, `kubernetes/` or `talos/` is
  refused with a pointer to the `.j2` source. So is a Bash command that writes there: a redirect target, a file given to `tee`, the destination of `cp`, `install` or
  `rsync` (or either end of `mv`, which removes its source), or a file given to `sd`, `sed -i`,
  `perl -pi`, `yq -i`/`--inplace` or `sops -i`/`--in-place`, in relative, `./`, `$PWD` or absolute
  form, quoted or not. Reading a rendered file
  and sending the result elsewhere is allowed.
- **Secrets files.** A Bash command segment that names `cluster.toml`, `age.key`, `deploy.key`,
  `cloudflare-tunnel.json`, `flux-webhook-token.txt`, `kubeconfig`, `talosconfig`, `secrets.yaml` (the Talos bundle)
  or `talos/rendered` (the machine configs `just talos render` writes, keys included) is refused
  unless that segment runs `template/scripts/validate.py`, `template/scripts/check_layout.py`, a
  `just template` recipe or `taplo check`. One shell tokenizer resolves quotes and reads nested
  shells, `eval` and command substitutions as commands, so a quoted, globbed or spliced name is
  still refused. Only a `git commit` message, a `grep` or `rg` pattern, a long flag's name such as
  `--kubeconfig` (its value still counts) and the body of a quoted heredoc (`<<'EOF'`) whose line
  runs only `cat`, `tee`, `gh` or `git commit` count as text; any other command on that line, an
  unknown interpreter included, makes the body commands again. An `rtk` prefix, with `bypass` or its
  flags, is looked through, by the allowed readers too. The Read tool is denied `cluster.toml` and the key files by `.claude/settings.json`.
- **The UniFi window.** Node maintenance is refused from 02:45 to 03:30 local time. That covers
  `just talos apply`, `apply-node`, `drain`, `stop-node`, `reboot-node`, `upgrade-node`, `upgrade-k8s` and
  `reset-node`, the all-node `upgrade` and `reset`, `talosctl` with
  `upgrade`, `reset`, `apply-config`, `reboot` or `shutdown`, `topf` with `apply`, `upgrade` or
  `reset`, and `kubectl drain`.

## Checks

```sh
claude plugin validate .claude/skills/cluster-guard
claude plugin test .claude/skills/cluster-guard
tsc -p .claude/skills/cluster-guard
```

`tsc -p` needs `.claude-plugin/types/`, which the engine lays beside a mod it hot-reloads and
which is gitignored. A `/reload-plugins` on 2.1.296 did not lay it (measured 2026-10-10). Without
it, copy the declarations from the bundled plugin-authoring skill into a scratch folder and point a
tsconfig at them and at `hooks/` and `tests/`, as the probe under
`docs/superpowers/specs/2026-10-10-mods-probe/tsconfig.external.json` does.
