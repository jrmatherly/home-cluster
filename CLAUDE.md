# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- AUTO-MANAGED: project-description -->

## Overview

A home Kubernetes cluster on Talos Linux, managed with Flux. The repo is a fork of `onedr0p/cluster-template`. You fill in one config file, `cluster.toml`, and makejinja renders it into the Talos, Kubernetes, Flux and bootstrap config.

- The repo is still at the template stage, so the template tooling is present. `just configure` has rendered `bootstrap/`, `kubernetes/`, `talos/` and `.sops.yaml`, and the cluster is bootstrapped and live. Flux reconciles `kubernetes/` from Git, so a config change reaches the cluster by re-rendering with `just configure`, then committing and pushing.
- `just template tidy` ends the template stage. It moves all template tooling to `.private/<timestamp>/`, and you cannot undo it.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: build-commands -->

## Build & Development Commands

`mise install` installs every pinned tool (`.mise/config.toml`, `.mise/conf.d/template.toml`). mise also sets `KUBECONFIG`, `TALOSCONFIG`, `SOPS_CONFIG` and `SOPS_AGE_KEY_FILE` to paths inside the repo. Run commands from the repo root.

Template stage:

- `just init` creates `cluster.toml` from `cluster.sample.toml`, plus `age.key`, `deploy.key` and `flux-webhook-token.txt`, skipping any that exist.
- `just configure` renders with makejinja, sops-encrypts every `*.sops.*` file, runs kubeconform on `kubernetes/`, and checks that topf can render `talos/`.
- `just template doctor` checks that the required files exist, that `cluster.toml` passes the schema, and that its sections follow the sample's order.
- `just template check-layout` checks that `cluster.toml` keeps its sections in the order of `cluster.sample.toml`. `just configure` runs it first.
- `just template schema` regenerates `cluster.schema.json` from the pydantic model.
- `just template scaffold <section>` copies a section's block from `cluster.sample.toml` into `cluster.toml` in the sample's position, keys left commented, printing line numbers only, then runs `check-layout`.
- `just template test-helmfile` renders the bootstrap Helm charts. It needs network access.
- `just template reset` deletes the rendered output.
- `uv run --locked pytest template/scripts/test_validate.py -q` runs the validator tests.
- `uv run --locked --no-dev template/scripts/validate.py <file.toml>` validates one config and prints it as JSON.
- `taplo check --schema "file://$PWD/cluster.schema.json" ./cluster.toml` checks the TOML against the schema.

These commands come from the rendered `mod.just` files, and now work:

- `just bootstrap talos` and `just bootstrap apps` run the two bootstrap phases.
- `just talos render|diff|apply|apply-node <node>|upgrade-node <node>|upgrade-k8s|reset-node <node>` manage the nodes. `just talos status|drain|uncordon|resume <node>` take one out of service and back by host name: `drain` checks the other nodes and etcd, switches over its CloudNativePG primaries (a one-instance cluster such as `ai-kb-db` is skipped with a warning and goes down with the node, since 2026-10-19; before that the drain aborted on it), then drains. `stop-node <node>` drains and powers it off for host maintenance, `reboot-node <node>` drains, reboots and resumes it, and `health` checks Talos, nodes, pods, Flux and CloudNativePG.
- `just kube primaries` lists the CloudNativePG primaries and their nodes, and `just kube switchover <cluster> <namespace> [replica]` promotes a replica with `kubectl cnpg promote` and waits for a healthy cluster.
- `just kube reconcile` forces a Flux reconcile.

Docs site (`docs/`, Nimbus on Astro): `docker build --build-context gitdir=.git --secret id=scrub_denylist,src=private/scrub-denylist.txt docs` lints, scrubs and builds the pages. `docs/scrub-check.sh` checks pages for private content, and lefthook runs it on staged pages under `docs/src/content`.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->

## Architecture

```text
cluster.sample.toml        documented config; copy to cluster.toml (gitignored)
cluster.schema.json        generated from validate.py; editors use it via the #:schema line
makejinja.toml             inputs template/overrides + template/config, output ./
justfile                   root; loads template/mod.just and the rendered mod.just files
template/
  config/                  *.j2 sources, mirrored into the repo root on render
    bootstrap/             helmfile/ (crds, apps), sops secrets, mod.just
    kubernetes/            apps/<namespace>/<app>/, components/sops, flux/cluster, mod.just
    talos/                 all/ (numbered patches), control-plane/, topf.yaml.j2, mod.just
  overrides/               extra makejinja input; *.partial.yaml.j2 are not rendered
  scripts/validate.py      pydantic model of cluster.toml: defaults, cross-field checks
  scripts/check_layout.py  section order of cluster.toml against the sample
  scripts/scaffold.py      copies a section block from the sample into cluster.toml
  scripts/plugin.py        makejinja Plugin: validated config as data; key and tunnel readers as functions
  scripts/test_validate.py pytest for the validator
  resources/kubeconform.sh validation run by `just configure`
  mod.just                 `just template ...` recipes
.github/template-tests/    valid/ and invalid/ cluster.toml fixtures, e2e/ helpers
.github/workflows/         template-e2e, template-e2e-cluster and template-release CI, plus label sync, flate, model-images, docs-image and update-apps
images/<model>/Dockerfile  model image recipes, built by the model-images workflow
docs/                      Nimbus (Astro) documentation site, Dockerfile and nginx.conf; built by docs-image.yaml
```

The data flows in one direction. `cluster.toml` goes through `validate.load()`, then `Plugin.data()`, then the makejinja render. The output lands in `bootstrap/`, `kubernetes/` and `talos/`, and Flux reconciles `kubernetes/` from Git.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->

## Code Conventions

- Edit the `.j2` source under `template/config/`, never the rendered copy. makejinja uses `#{ var }#` and `#% block %#`, and plain `{{ }}` passes through to the output.
- Area rules in `.claude/rules/` load when you open matching files. `templates.md` covers makejinja, `talos.md` covers topf and Talos patches, `flux-apps.md` covers the Flux app layout, `validator.md` covers schema changes, `docs.md` covers docs pages, and `apps/` holds one file per app or platform area.
- Renovate updates chart and image versions in `.yaml.j2` files on its own. `# renovate:` comments are only for the pins its managers cannot find: the Talos and Kubernetes versions in `talos/topf.yaml.j2`, and the `prometheus-operator-crds` chart in `bootstrap/helmfile/crds.yaml.j2`. `.renovaterc.json5` holds Sonarr below 5 until upstream marks a v5 tag Latest, and InfluxDB below 3, which is a different database. Its three "Tier 1 automerge" rules merge digest PRs, patch PRs for an allowlist of version-only apps and the docs Dockerfile digests on the weekend in PR mode, and Flate is the only check on a Renovate branch under `kubernetes/**`.
- Formatting follows `.editorconfig`: 2 spaces, LF line endings, 4 spaces for Markdown and shell. oxfmt formats YAML, JSON, Markdown and TOML at width 100 across the whole tree, minus `.oxfmtrc.json`'s `ignorePatterns`, so TOML has no aligned `=` columns; the pre-commit hook formats staged files, and the stop hook and CI run `oxfmt --check .`.
- Python: `validate.py` subclasses `Model` (`extra="forbid"`), uses `Annotated` validators, and reports errors through `ConfigError` and `format_errors`, one per line. `plugin.py` uses single quotes, and `validate.py` uses double quotes.
- just recipes use `[doc()]`, `[group()]` and `[private]` attributes, and run under bash with `-euo pipefail`. They log through `just log <level> "<msg>" key value`, which calls `gum log`.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->

## Detected Patterns

- A `cluster.toml` schema change touches four places: `validate.py`, `cluster.sample.toml`, `cluster.schema.json` (from `just template schema`), and the test fixtures. `.claude/rules/validator.md` has the steps, and each invalid fixture carries a `# expect: <error message>` line that `test_invalid_fixture_rejected` matches. `cluster.sample.toml` is the layout of record: `cluster.toml` and the fixtures keep its section order and banner comments, a new section is scaffolded into `cluster.toml` by copying the sample's block into the same position, and `just template check-layout` fails a config whose sections are out of that order.
- Rendered YAML has to be oxfmt-clean: the Stop hook runs `oxfmt --check .` on the whole tree and on every fixture's render, and the lefthook pre-commit hook formats staged files (the upstream CI step that checks it skips on this fork).
- Facts about one app or platform area live in `.claude/rules/apps/<name>.md`, which load when you touch its templates: `localai`, `model-images`, `restart-reset`, `flux-alerts`, `github-runner`, `bootstrap-charts`, `storage`, `postgres`, `observability`, `unifi-dns`, `pocket-id`, `radar`, `matherlynet`, `hubble`, `reactive-resume`, `redis`, `kener`, `network-optimizer`, `pegaprox`, `actual-budget`, `media`, `ai-workspace`, `ai-kb`, `rustfs`, `langfuse`, `docs-site`. Read the file by hand before changing its section in `validate.py` or `cluster.sample.toml`, or when another app depends on it.
- Every file with `.sops.` in its name is encrypted in place during `just configure`.
- Re-running `just configure` re-encrypts every `*.sops.*` file with new ciphertext, even when the plaintext is unchanged, so they show as modified after any re-render. When the secret inputs did not change, restore them with `git checkout -- ':(glob)bootstrap/**/*.sops.*' ':(glob)kubernetes/**/*.sops.*' ':(glob)talos/**/*.sops.*'` before committing. Keep the directory prefixes: a bare `**/*.sops.*` also matches the `*.sops.*.j2` templates and discards uncommitted edits to them. `just configure` logs a warning with the count of re-encrypted `*.sops.*` files and this restore command (`sops_pathspec` in `template/mod.just`).

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: git-insights -->

## Git Insights

- History starts with a single `Initial commit`, imported from the upstream template.
- The template-e2e and template-e2e-cluster jobs only run when `github.repository == 'onedr0p/cluster-template'`. On this fork they skip, so run the checks locally. `template-release.yaml` has no such guard and runs monthly.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: best-practices -->

## Best Practices

- Never commit secrets or machine config. `.gitignore` covers `cluster.toml`, `age.key`, `deploy.key`, `flux-webhook-token.txt`, `cloudflare-tunnel.json`, `kubeconfig` and `talosconfig`.
- The Stop hook (`.claude/hooks/stop.py`) blocks the end of a turn while template changes fail. It runs when anything under `template/`, the sample, the schema, `makejinja.toml`, `pyproject.toml`, `uv.lock` or `.github/template-tests/` differs from `main` (on `main` itself, from HEAD, so a committed break is not re-checked). It runs `oxfmt --check .` on the working tree, and in a scratch copy runs pytest, renders every valid fixture and format-checks the output, and runs kubeconform and topf on the `public` fixture only; kubeconform is skipped offline, a second Stop with the same unchanged failure is let through, and the hook fails open on its own errors. For workflow changes, run `zizmor --offline .github/workflows/*.yaml` yourself.
- `.claude/settings.json` blocks reading the key files and asks before destructive commands: `reset`, `tidy`, `bootstrap`, `apply`, `upgrade`, `sops decrypt`, `kubectl delete`, and similar. rtk's Claude Code hook rewrites commands before those rules and the sandbox exclusions read them, so `exclude_commands` in `~/Library/Application Support/rtk/config.toml` must list `just`, `sops`, `gh`, `kubectl` and `helm` (measured 2026-10-31: without it a rewritten `gh pr close` skipped its `ask` rule). Serena's write tools are denied and `run_in_terminal` asks, because cluster-guard sees only Edit, Write and Bash. Don't work around a prompt, for example with `yes |` or `--yes`.
- The `cluster-guard` mod (`.claude/skills/cluster-guard/`, see its README) is a hooks module that refuses Edit/Write/Bash writes into the rendered `bootstrap/`, `kubernetes/` and `talos/` trees (since 2026-10-10 a rendered path counts as a write only where the command writes it: a redirect target, a file given to `tee`, the destination of `cp`, either end of `mv`, or a file given to `sd`, `sed -i`, `perl -pi`, `yq -i`/`--inplace` or `sops -i`/`--in-place`, the root `.sops.yaml` included, in relative, `./`, `$PWD`, absolute or quoted form, so reading one into scratch is allowed; the mod's tests run from lefthook whenever its files are staged), refuses any Bash command segment that names `cluster.toml`, `age.key`, `deploy.key`, `cloudflare-tunnel.json`, `flux-webhook-token.txt`, `kubeconfig` or `talosconfig` outside `validate.py`, `check_layout.py`, `just template` recipes and `taplo check`, refuses node maintenance (the `just talos` drain, apply, apply-node, upgrade-node, upgrade-k8s, reset-node, stop-node and reboot-node recipes and the all-node `upgrade` and `reset`, plus raw `talosctl`, `topf` and `kubectl drain`) from 02:45 to 03:30 local, and counts re-encrypted `*.sops.*` files after configure, add, commit, restore, stash and checkout. The gitignored `.claude/skills/cluster-guard/.claude-plugin/types/` is where Claude Code lays type declarations for a mod it hot-reloads; `/reload-plugins` did not lay it, and a plugin folder added while a session is open loads only after that session restarts or runs `/reload-plugins` (both measured 2026-10-10). `.claude/settings.json` denies `Read(/cluster.toml)`, and the gitignored `.claude/settings.local.json` re-allows `./cluster.toml` for the sandbox so the parser path works.
- lefthook runs these on pre-commit: oxfmt, `just --fmt`, `mise fmt`, `mise lock`, zizmor, Ruff, shellcheck, markdownlint, `docs/scrub-check.sh` on staged pages under `docs/src/content`, `claude plugin test` on `cluster-guard` when its files are staged, and a size check that fails a `CLAUDE.md` over 20,000 characters. The `format-toml` job excludes `.mise/**`, because `.oxfmtrc.json` ignores that tree and oxfmt exits 2 when every file it is given is ignored (`mise fmt` formats those files); the `format-json` job excludes `docs/package-lock.json` for the same reason, because oxfmt ignores lockfiles and a lockfile-only commit would fail. After you edit a mise config, commit the updated `.mise/mise.lock`.
- On macOS, use `sd` for regex replacements instead of `sed -i`.

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->

## Custom Notes

A fact about one app goes in `.claude/rules/apps/<name>.md`, never in this file or its auto-managed sections, because this file loads in every session. A new `cluster.toml` section gets its own rule file, with `paths` on its namespace, and a name in the index line under Detected Patterns.

<!-- END MANUAL -->
