# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- AUTO-MANAGED: project-description -->

## Overview

A home Kubernetes cluster on Talos Linux, managed with Flux. The repo is a fork of `onedr0p/cluster-template`. You fill in one config file, `cluster.toml`, and makejinja renders it into the Talos, Kubernetes, Flux and bootstrap config.

- The repo is still at the template stage. The rendered directories `bootstrap/`, `kubernetes/`, `talos/` and the `.sops.yaml` file do not exist until `just configure` runs.
- `just template tidy` ends the template stage. It moves all template tooling to `.private/<timestamp>/`, and you cannot undo it.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: build-commands -->

## Build & Development Commands

`mise install` installs every pinned tool (`.mise/config.toml`, `.mise/conf.d/template.toml`). mise also sets `KUBECONFIG`, `TALOSCONFIG`, `SOPS_CONFIG` and `SOPS_AGE_KEY_FILE` to paths inside the repo. Run commands from the repo root.

Template stage:

- `just init` creates `cluster.toml` from `cluster.sample.toml`, plus `age.key`, `deploy.key` and `flux-webhook-token.txt`, skipping any that exist.
- `just configure` renders with makejinja, sops-encrypts every `*.sops.*` file, runs kubeconform on `kubernetes/`, and checks that topf can render `talos/`.
- `just template doctor` checks that the required files exist and that `cluster.toml` passes the schema.
- `just template schema` regenerates `cluster.schema.json` from the pydantic model.
- `just template test-helmfile` renders the bootstrap Helm charts. It needs network access.
- `just template reset` deletes the rendered output.
- `uv run --locked pytest template/scripts/test_validate.py -q` runs the validator tests.
- `uv run --locked --no-dev template/scripts/validate.py <file.toml>` validates one config and prints it as JSON.
- `taplo check --schema "file://$PWD/cluster.schema.json" ./cluster.toml` checks the TOML against the schema.

These commands exist only after rendering:

- `just bootstrap talos` and `just bootstrap apps` run the two bootstrap phases.
- `just talos render|diff|apply|apply-node <node>|upgrade-node <node>|upgrade-k8s|reset-node <node>` manage the nodes.
- `just kube reconcile` forces a Flux reconcile.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: architecture -->

## Architecture

```
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
  scripts/plugin.py        makejinja Plugin: validated config, keys, tunnel secrets as template data
  scripts/test_validate.py pytest for the validator
  resources/kubeconform.sh validation run by `just configure`
  mod.just                 `just template ...` recipes
.github/template-tests/    valid/ and invalid/ cluster.toml fixtures, e2e/ helpers
.github/workflows/         template-e2e and template-release CI, plus label sync and flate
```

The data flows in one direction. `cluster.toml` goes through `validate.load()`, then `Plugin.data()`, then the makejinja render. The output lands in `bootstrap/`, `kubernetes/` and `talos/`, and Flux reconciles `kubernetes/` from Git.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->

## Code Conventions

- Edit the `.j2` source under `template/config/`, never the rendered copy.
- makejinja uses custom delimiters. A variable is `#{ var }#`, a block is `#% ... %#`, and a comment is `#| ... #|`. Plain `{{ }}` passes through to the output unchanged. Topf Go templates (`{{ .Node.Host }}` in `*.tpl.j2`) and Flux `${VAR}` substitution rely on that.
- `undefined = "strict"`. Any unknown variable fails the render.
- Template variables are fields of the validated config, as in `#{ kubernetes.api.addr }#` and `#% for item in nodes %#`.
- Talos patches in `template/config/talos/all/` start with a two-digit number that sets their order. A `.yaml.tpl.j2` file becomes a per-node topf template.
- Each Flux app lives at `apps/<namespace>/<app>/ks.yaml.j2`, with its `app/` directory holding `helmrelease`, `kustomization` and `ocirepository` files.
- Pin each version in a template with a `# renovate: datasource=... depName=...` comment on the line above it.
- Formatting follows `.editorconfig`: 2 spaces, LF line endings, 4 spaces for Markdown and shell. oxfmt formats YAML, JSON and Markdown at width 100.
- Python: `validate.py` subclasses `Model` (`extra="forbid"`), uses `Annotated` validators, and reports errors through `ConfigError` and `format_errors`, one per line. `plugin.py` uses single quotes, and `validate.py` uses double quotes.
- just recipes use `[doc()]`, `[group()]` and `[private]` attributes, and run under bash with `-euo pipefail`. They log through `just log <level> "<msg>" key value`, which calls `gum log`.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->

## Detected Patterns

- A `cluster.toml` schema change touches four places. Update `validate.py`, update the docs in `cluster.sample.toml`, run `just template schema`, and add fixtures under `.github/template-tests/`. The tests fail when `cluster.schema.json` drifts from the model.
- When you add an invalid fixture, also add its name to the `validate-invalid` matrix in `.github/workflows/template-e2e.yaml`.
- Rendered YAML has to be oxfmt-clean, because CI runs `oxfmt --check` on the rendered directories. Write templates so they render already formatted.
- Every file with `.sops.` in its name is encrypted in place during `just configure`.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: git-insights -->

## Git Insights

- History starts with a single `Initial commit`, imported from the upstream template.
- The template CI jobs only run when `github.repository == 'onedr0p/cluster-template'`. On this fork they skip, so run the checks locally.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: best-practices -->

## Best Practices

- Never commit secrets or machine config. `.gitignore` covers `cluster.toml`, `age.key`, `deploy.key`, `flux-webhook-token.txt`, `cloudflare-tunnel.json`, `kubeconfig` and `talosconfig`.
- Before you finish a change, run the checks that match it:
    - For validator changes, run pytest and then `just template schema`.
    - For template changes, run `just configure`, then `oxfmt --check ./.sops.yaml ./bootstrap ./kubernetes ./talos`.
    - For workflow changes, run `zizmor --offline .github/workflows/*.yaml`.
- lefthook runs these on pre-commit: oxfmt, `just --fmt`, `mise fmt`, and `mise lock`. After you edit a mise config, commit the updated `.mise/mise.lock`.
- On macOS, use `sd` for regex replacements instead of `sed -i`.

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->

## Custom Notes

Add project-specific notes here. This section is never auto-modified.

<!-- END MANUAL -->
