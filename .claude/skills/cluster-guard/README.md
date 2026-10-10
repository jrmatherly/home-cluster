# cluster-guard

A Claude Code hooks module for this repo. It refuses four things before the tool runs:

- **Rendered files.** An Edit or Write under `bootstrap/`, `kubernetes/` or `talos/`, or on the
  root `.sops.yaml`, is refused with a pointer to the `.j2` source. So is a Bash command that
  redirects into those directories or names a path there as the operand of `tee`, `cp`, `mv`,
  `sd`, `sed -i`, `yq -i` or `sops -i`.
- **Secrets files.** A Bash command segment that names `cluster.toml`, `age.key`, `deploy.key`,
  `cloudflare-tunnel.json`, `flux-webhook-token.txt`, `kubeconfig` or `talosconfig` is refused
  unless that segment runs `template/scripts/validate.py`, `template/scripts/check_layout.py`, a
  `just template` recipe or `taplo check`. Segments are split on `;`, `&&`, `||`, `|` and
  newlines, and quoted text is ignored, so a commit message or a quoted grep pattern may name the
  file. The Read tool is denied `cluster.toml` and the key files by `.claude/settings.json`.
- **The UniFi window.** Node maintenance is refused from 02:45 to 03:30 local time. That covers
  `just talos apply` and the drain, stop, reboot, upgrade and reset recipes, `talosctl` with
  `upgrade`, `reset`, `apply-config`, `reboot` or `shutdown`, `topf` with `apply`, `upgrade` or
  `reset`, and `kubectl drain`.
- **sops churn.** After `just configure`, `git add`, `git commit`, `git restore`, `git stash` or
  `git checkout`, it counts the modified `*.sops.*` files under the three rendered directories and
  shows the count on a pinned line, or clears it. A commit that carries them (staged, or any with
  `-a`) also raises a toast.

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
