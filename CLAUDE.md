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
- Renovate updates chart and image versions in `.yaml.j2` files on its own. `# renovate:` comments are only for the pins its managers cannot find: the Talos and Kubernetes versions in `talos/topf.yaml.j2`, and the `prometheus-operator-crds` chart in `bootstrap/helmfile/crds.yaml.j2`.
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
- `[postgres.backup]` in `cluster.toml` (endpoint, bucket and an access key pair, set all together or not at all) is the object store for Postgres backups. `components/postgres` renders only when it is set. An app with a database includes that component from its `app/kustomization.yaml`, which adds the `postgres-backup` ObjectStore and Secret and the `postgresql` ImageCatalog to the app's namespace, and its `ks.yaml` depends on `cloudnative-pg` and `plugin-barman-cloud` in `cnpg-system`. Backups land under the Cluster's name in the bucket, so Cluster names must be unique across namespaces. The component also adds a `postgres` PodMonitor that scrapes every instance in the namespace, and `cnpg-system/cloudnative-pg` holds the `postgres-backup` PrometheusRule (backup failed, backup older than 36 hours, WAL archiving failing). Its rules use the plugin's `barman_cloud_cloudnative_pg_io_*` metrics, because the `cnpg_collector_*` backup metrics stay at 0 with the plugin. The `public` fixture sets the section.
- `[observability]` in `cluster.toml` (a Grafana password, an InfluxDB password and an InfluxDB token, set all together or not at all) gates the whole `observability` namespace, which enforces the `privileged` pod security level for node-exporter. `kube-prometheus-stack` runs Prometheus, Alertmanager and Grafana, scrapes every ServiceMonitor, PodMonitor and rule in the cluster, and reaches etcd through the control-plane node addresses. `influxdb` is InfluxDB 2 on the app-template chart, with org `home` and bucket `proxmox` created on the first start. Grafana and InfluxDB have routes on the internal gateway. Prometheus and Grafana have memory requests and limits set in the HelmRelease. The optional `discord_webhook` field, which needs the other three, gives Alertmanager a Discord receiver that reads the URL from the mounted `alertmanager-secret`; without it every alert goes to the `null` receiver. The optional `grafana_oidc_client_id` and `grafana_oidc_client_secret` pair (an OIDC client created by hand in Pocket ID, needing `[pocket_id]`) adds a Pocket ID sign-in to Grafana next to the password form; only the Pocket ID group `cluster_admins` gets a role, as Grafana server admin, and everyone else is refused. The `public` fixture sets the section.
- `[unifi]` in `cluster.toml` (the console address and an API key, set together or not at all) gates `network/unifi-dns`, a second ExternalDNS with the UniFi webhook sidecar. It writes local DNS records to the console for routes on `envoy-internal`, and for the gateways' own names through the `service` source, so internal names resolve on the LAN without manual records. `cloudflare-dns` keeps handling `envoy-external`. When `unifi.host` is an IPv4 address, CoreDNS also forwards lookups for the domain to the console, with the node resolvers after it as a fallback, so pods resolve the names that exist only on the internal gateway. That forward is a second `forward` in the main server block, not a server block of its own, because `autopath` resolves a pod's search path inside the main block and would bypass a separate one. The `public` fixture sets the section.
- `[pocket_id]` in `cluster.toml` (an encryption key, which needs `[postgres.backup]`) gates the `security` namespace, which enforces the `restricted` pod security level. `security/pocket-id` is Pocket ID, a passkey OpenID Connect provider, on the app-template chart at `auth.${SECRET_DOMAIN}` on the internal gateway. Passkeys are bound to that hostname, so it must not change. Its state is in the CloudNativePG cluster `pocket-id-db` (two instances, WAL archiving and a daily backup), so the pod has no volume. The same flag adds a `hosts` entry to CoreDNS that answers `auth.${SECRET_DOMAIN}` with the internal gateway, because pods cannot resolve names that exist only on the internal gateway. The optional `public = true` (needing an ingress mode other than `none`) also attaches the route to `envoy-external`, so `cloudflare-dns` publishes it and the internet reaches the sign-in page and API through the tunnel, while LAN clients and pods keep the internal path. The `public` fixture sets the section.
- `[radar]` in `cluster.toml` (the ID and secret of an OIDC client created by hand in Pocket ID, set together or not at all, and needing `[pocket_id]`) gates the `radar` namespace, which enforces the `restricted` pod security level. `radar/radar` is Radar, a Kubernetes UI, from its own chart at `radar.${SECRET_DOMAIN}` on the internal gateway. It signs users in with Pocket ID itself (`auth.mode: oidc`) and acts as the signed-in user through impersonation, so its ServiceAccount can read every Secret and impersonate anyone: treat the pod as cluster-admin. What a user may do comes from `clusterrolebinding.yaml`, which binds the Pocket ID group `cluster_admins` (as `oidc:cluster_admins`) to `cluster-admin`. Its timeline is in the CloudNativePG cluster `radar-db` (two instances, no backup). The `public` fixture sets the section.
- `[matherlynet]` in `cluster.toml` (a session secret and an admin email, set together, needing `[postgres.backup]` and the Cloudflare tunnel) gates the `matherlynet` namespace, which enforces the `restricted` pod security level. The optional `smtp_url` must be a `smtp://` or `smtps://` URL, because the site's mail library throws on a bare host name. `matherlynet/matherlynet` is the public site at the domain's apex, from its own chart (`ghcr.io/jrmatherly/matherlynet/charts/matherlynet`, built from the `~/dev/matherlynet` repo), with `www` redirecting to it, both on the external gateway. The chart cannot emit a securityContext, resources or annotations, so the HelmRelease adds them with a `postRenderers` patch. Its data is in the CloudNativePG cluster `matherlynet-db` (two instances, WAL archiving and a daily backup), whose generated connection string reaches the chart through `valuesFrom`. A NetworkPolicy admits only the `network` namespace, because the site trusts Cloudflare's client address header. The tunnel gets an apex rule, since its wildcard does not match the apex. ExternalDNS creates the apex record but cannot own it (see the comment in `httproute.yaml.j2`). `playground = true` labels the namespace as a llama-server client and sets the model URL. The `public` fixture sets the section.
- `[cilium.hubble]` in `cluster.toml` (the ID and secret of an OIDC client created by hand in Pocket ID, set together, needing `[pocket_id]`) turns on Hubble, its relay and its UI in the Cilium release, with the UI at `hubble.${SECRET_DOMAIN}` on the internal gateway. Hubble UI has no login, so an Envoy Gateway `SecurityPolicy` on its route signs users in with Pocket ID, then verifies the ID token from a cookie and admits only the `cluster_admins` group. Hubble's certificates use the chart's `cronJob` method, because the default `helm` method keeps the certificates it finds and they would expire after a year. Turning the section on or off restarts the Cilium agent on every node. The `public` fixture sets the section.
- `[reactive_resume]` in `cluster.toml` (an auth secret, an encryption secret of at least 32 characters, the ID and secret of an OIDC client created by hand in Pocket ID, and an S3 endpoint, bucket and key pair, set all together, needing `[pocket_id]` and an ingress mode other than `none`) gates the `reactive-resume` namespace, which enforces the `restricted` pod security level. `reactive-resume/reactive-resume` is Reactive Resume v6, a resume builder, on the app-template chart at `resume.${SECRET_DOMAIN}` on the external gateway. Pocket ID is its only login (`FLAG_DISABLE_EMAIL_AUTH`), and a first Pocket ID sign-in creates the account. Uploads go to the S3 bucket, which must exist first; the endpoint is in the sops Secret because it holds the Cloudflare account ID. Its data is in the CloudNativePG cluster `reactive-resume-db` (two instances, WAL archiving and a daily backup at 04:00). `TRUSTED_PROXIES` is the pod CIDR, so the app reads the client address from `X-Forwarded-For`, and a NetworkPolicy admits only the `network` namespace for that reason. Its probes request `/`, not `/api/health`, because that check writes to the bucket inside a fixed 1.5 s limit and a slow bucket would take the only pod out of the Service; an init container holds the app back until the database accepts connections. Never change `auth_secret` (signs everyone out, breaks two-factor secrets) or `encryption_secret` (saved AI keys become unreadable). The `public` fixture sets the section.
- `[redis]` in `cluster.toml` (one password of at least 24 letters and digits) gates `components/redis`, the Redis counterpart of `components/postgres`. An app that needs Redis includes the component from its `app/kustomization.yaml` and gets an instance of its own in its namespace: a `redis` StatefulSet (Redis 8, one replica, an append-only file on a 1Gi `local-path` volume, no eviction), a `redis` Service, the `redis-auth` Secret and a NetworkPolicy that admits only the same namespace. So there is at most one per namespace, at `redis:6379`. The server reads the password from a mounted `redis.conf`, so it never appears in the process arguments, and a client builds its URL from the `password` key. Instances are never shared between apps, because eviction policy, key names and blast radius differ per consumer. The `public` fixture sets the section.
- `[kener]` in `cluster.toml` (a secret key of at least 32 characters, needing `[postgres.backup]`, `[redis]` and an ingress mode other than `none`) gates the `kener` namespace, which enforces the `restricted` pod security level. `kener/kener` is Kener, a status page with uptime monitoring, on the app-template chart at `status.${SECRET_DOMAIN}`. The internal gateway serves all of it. The external gateway serves the status page and answers 404 for `/manage`, `/account` and `/api` through an Envoy Gateway `HTTPRouteFilter`, because the first visitor to a new instance creates the admin account, the sign-in form has no rate limit, and an admin can point a monitor at any address. Its job queue is the namespace's Redis from `components/redis`. Kener keeps its check schedule there and only writes it at startup, so if Redis ever comes back empty every check stops while `/healthcheck` still answers ok, and Kener needs a restart. An init container copies the image's ping, which drops its `NET_RAW` file capability, and the copy is mounted over the original, because the original cannot start under `restricted` and every ping monitor would fail. Its data is in the CloudNativePG cluster `kener-db` (two instances, WAL archiving and a daily backup at 04:30). Single sign-on is set up in Kener's admin UI and stored in its database, not in this repo. The optional `smtp_url` and `mail_from` pair is split into the `SMTP_*` settings Kener reads (`kener_smtp`), all in the sops Secret. The `public` fixture sets the section.
- `[network_optimizer]` in `cluster.toml` (an admin password of at least 8 characters with a digit, needing `[observability]`) gates the `network-optimizer` namespace, which enforces the `restricted` pod security level. `network-optimizer/network-optimizer` is Network Optimizer, which audits and monitors the UniFi network and writes time series to the InfluxDB in `observability`, on the app-template chart at `optimizer.${SECRET_DOMAIN}` on the internal gateway only. The image's entrypoint runs as root, so the HelmRelease runs `dotnet NetworkOptimizer.Web.dll` as UID 1654 and sets `ASPNETCORE_URLS` itself. An init container copies the image's `ping` and `traceroute.db`, which carry the `NET_RAW` file capability and cannot start under `restricted`, and the copies are mounted over the originals; the pod sysctl `net.ipv4.ping_group_range` lets the copies open an ICMP socket instead. `HOST_IP` stays unset, because it is the LAN address that path analysis starts from and a pod has none. A `CiliumNetworkPolicy` admits ICMP Time Exceeded and Destination Unreachable from outside the cluster, because the NetworkPolicy would otherwise drop the replies the app's traceroutes depend on and a Kubernetes NetworkPolicy cannot name ICMP. Its SQLite database and keys are on a 5Gi `local-path` volume at `/app/data`, so the Deployment uses `Recreate`. The optional `oidc_client_id` and `oidc_client_secret` pair (an OIDC client created by hand in Pocket ID with the callback `/signin-oidc/pocket-id`, needing `[pocket_id]`) renders `/app/config/identity.json`, which the app applies at boot; the client secret is not in that file but in `NETOPT_FED_POCKET_ID_SECRET`. The UniFi API key, the InfluxDB connection and the Pocket ID role mapping are entered in the app's Settings and live in its SQLite database, not in this repo; `cluster.sample.toml` lists those steps. The `public` fixture sets the section.
- Every file with `.sops.` in its name is encrypted in place during `just configure`.
- Re-running `just configure` re-encrypts every `*.sops.*` file with new ciphertext, even when the plaintext is unchanged, so they show as modified after any re-render. When the secret inputs did not change, restore them with `git checkout -- ':(glob)bootstrap/**/*.sops.*' ':(glob)kubernetes/**/*.sops.*' ':(glob)talos/**/*.sops.*'` before committing. Keep the directory prefixes: a bare `**/*.sops.*` also matches the `*.sops.*.j2` templates and discards uncommitted edits to them.

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
