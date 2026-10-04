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
- `just template doctor` checks that the required files exist and that `cluster.toml` passes the schema.
- `just template schema` regenerates `cluster.schema.json` from the pydantic model.
- `just template test-helmfile` renders the bootstrap Helm charts. It needs network access.
- `just template reset` deletes the rendered output.
- `uv run --locked pytest template/scripts/test_validate.py -q` runs the validator tests.
- `uv run --locked --no-dev template/scripts/validate.py <file.toml>` validates one config and prints it as JSON.
- `taplo check --schema "file://$PWD/cluster.schema.json" ./cluster.toml` checks the TOML against the schema.

These commands come from the rendered `mod.just` files, and now work:

- `just bootstrap talos` and `just bootstrap apps` run the two bootstrap phases.
- `just talos render|diff|apply|apply-node <node>|upgrade-node <node>|upgrade-k8s|reset-node <node>` manage the nodes.
- `just kube reconcile` forces a Flux reconcile.

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
  scripts/plugin.py        makejinja Plugin: validated config, keys, tunnel secrets as template data
  scripts/test_validate.py pytest for the validator
  resources/kubeconform.sh validation run by `just configure`
  mod.just                 `just template ...` recipes
.github/template-tests/    valid/ and invalid/ cluster.toml fixtures, e2e/ helpers
.github/workflows/         template-e2e and template-release CI, plus label sync, flate and model-images
images/<model>/Dockerfile  model image recipes, built by the model-images workflow
```

The data flows in one direction. `cluster.toml` goes through `validate.load()`, then `Plugin.data()`, then the makejinja render. The output lands in `bootstrap/`, `kubernetes/` and `talos/`, and Flux reconciles `kubernetes/` from Git.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: conventions -->

## Code Conventions

- Edit the `.j2` source under `template/config/`, never the rendered copy. makejinja uses `#{ var }#` and `#% block %#`, and plain `{{ }}` passes through to the output.
- Area rules in `.claude/rules/` load when you open matching files. `templates.md` covers makejinja, `talos.md` covers topf and Talos patches, `flux-apps.md` covers the Flux app layout, and `validator.md` covers schema changes.
- Renovate updates chart and image versions in `.yaml.j2` files on its own. `# renovate:` comments are only for the Talos and Kubernetes versions in `talos/topf.yaml.j2`.
- Formatting follows `.editorconfig`: 2 spaces, LF line endings, 4 spaces for Markdown and shell. oxfmt formats YAML, JSON and Markdown at width 100.
- Python: `validate.py` subclasses `Model` (`extra="forbid"`), uses `Annotated` validators, and reports errors through `ConfigError` and `format_errors`, one per line. `plugin.py` uses single quotes, and `validate.py` uses double quotes.
- just recipes use `[doc()]`, `[group()]` and `[private]` attributes, and run under bash with `-euo pipefail`. They log through `just log <level> "<msg>" key value`, which calls `gum log`.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: patterns -->

## Detected Patterns

- A `cluster.toml` schema change touches four places: `validate.py`, `cluster.sample.toml`, `cluster.schema.json` (from `just template schema`), and the test fixtures. `.claude/rules/validator.md` has the steps.
- Rendered YAML has to be oxfmt-clean, because CI runs `oxfmt --check` on the rendered directories.
- The whole `ai` namespace (`ai/llama-server` and its namespace and kustomization files) is wrapped in `#% if nvidia_enabled %#`, so it renders empty when NVIDIA is off.
- llama-server's image is pinned as `tag@sha256:digest`, and a Renovate rule in `.renovaterc.json5` keeps it on the `server-cuda-v<semver>` CUDA 12 tags. Its startup probe sends a real chat request so the pod is Ready only when warm, and a NetworkPolicy admits only the `ai` namespace and namespaces labelled `llama-server.ai/client: "true"`.
- `images/<model>/Dockerfile` is the recipe for a model image that llama-server mounts as an image volume. It downloads the GGUF from Hugging Face at a pinned `REVISION`, checks `SHA256`, and copies it into a `scratch` image. The Model Images workflow (`.github/workflows/model-images.yaml`) builds and pushes it to `ghcr.io/jrmatherly/models/<model>` when `images/**` changes on `main`, and never rebuilds a tag that exists. When the pin changes, update `REVISION`, `FILE`, `SHA256` and `TAG` (`<quant>-<first 7 chars of REVISION>`) together, then put the digest from the run summary in the HelmRelease.
- `storage/local-path-provisioner` provides the default StorageClass `local-path`. Its volumes are directories under `/var/mnt/local-path`, declared as a Talos `UserVolumeConfig` in `talos/all/72-volumes.yaml`, so each volume is pinned to one node and has no size limit.
- `cnpg-system` holds the CloudNativePG operator (`cloudnative-pg`) and its backup plugin (`plugin-barman-cloud`). The plugin must run in the operator's namespace, and its TLS certificates come from cert-manager. The namespace enforces the `restricted` pod security level.
- `[postgres.backup]` in `cluster.toml` (endpoint, bucket and an access key pair, set all together or not at all) is the object store for Postgres backups. `components/postgres` renders only when it is set. An app with a database includes that component from its `app/kustomization.yaml`, which adds the `postgres-backup` ObjectStore and Secret and the `postgresql` ImageCatalog to the app's namespace, and its `ks.yaml` depends on `cloudnative-pg` and `plugin-barman-cloud` in `cnpg-system`. Backups land under the Cluster's name in the bucket, so Cluster names must be unique across namespaces. The `public` fixture sets the section.
- `[observability]` in `cluster.toml` (a Grafana password, an InfluxDB password and an InfluxDB token, set all together or not at all) gates the whole `observability` namespace, which enforces the `privileged` pod security level for node-exporter. `kube-prometheus-stack` runs Prometheus, Alertmanager and Grafana, scrapes every ServiceMonitor, PodMonitor and rule in the cluster, and reaches etcd through the control-plane node addresses. `influxdb` is InfluxDB 2 on the app-template chart, with org `home` and bucket `proxmox` created on the first start. Grafana and InfluxDB have routes on the internal gateway. The `public` fixture sets the section.
- Every file with `.sops.` in its name is encrypted in place during `just configure`.
- Re-running `just configure` re-encrypts every `*.sops.*` file with new ciphertext, even when the plaintext is unchanged, so they show as modified after any re-render. When the secret inputs did not change, restore them with `git checkout -- ':(glob)**/*.sops.*'` before committing.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: git-insights -->

## Git Insights

- History starts with a single `Initial commit`, imported from the upstream template.
- The template CI jobs only run when `github.repository == 'onedr0p/cluster-template'`. On this fork they skip, so run the checks locally.

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: best-practices -->

## Best Practices

- Never commit secrets or machine config. `.gitignore` covers `cluster.toml`, `age.key`, `deploy.key`, `flux-webhook-token.txt`, `cloudflare-tunnel.json`, `kubeconfig` and `talosconfig`.
- The Stop hook (`.claude/hooks/stop.py`) blocks the end of a turn while template changes fail. It renders every valid fixture, runs oxfmt, kubeconform, and topf, and runs pytest when `template/scripts/` changed. For workflow changes, run `zizmor --offline .github/workflows/*.yaml` yourself.
- `.claude/settings.json` blocks reading the key files and asks before destructive commands: `reset`, `tidy`, `bootstrap`, `apply`, `upgrade`, `sops decrypt`, `kubectl delete`, and similar. Don't work around a prompt, for example with `yes |` or `--yes`.
- lefthook runs these on pre-commit: oxfmt, `just --fmt`, `mise fmt`, `mise lock`, zizmor, Ruff, shellcheck, and markdownlint. After you edit a mise config, commit the updated `.mise/mise.lock`.
- On macOS, use `sd` for regex replacements instead of `sed -i`.

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->

## Custom Notes

Add project-specific notes here. This section is never auto-modified.

<!-- END MANUAL -->
