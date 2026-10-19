# Per-app notes

One row per app this repo templates. Add a row when an app is added, and add a note when an update teaches
something. Step 5 of the skill keeps this file current.

## Upstream sources

The chart column is what the template pins. The releases column is where the notes are.

| App                       | Namespace          | Chart pinned                                                                                      | Release notes                                                     |
| ------------------------- | ------------------ | ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| cilium                    | kube-system        | `quay.io/cilium/charts/cilium`                                                                    | <https://github.com/cilium/cilium/releases>                       |
| coredns                   | kube-system        | `ghcr.io/coredns/charts/coredns`                                                                  | <https://github.com/coredns/helm/releases>                        |
| metrics-server            | kube-system        | `ghcr.io/home-operations/charts-mirror/metrics-server`                                            | <https://github.com/kubernetes-sigs/metrics-server/releases>      |
| nvidia-device-plugin      | kube-system        | `ghcr.io/home-operations/charts-mirror/nvidia-device-plugin`                                      | <https://github.com/NVIDIA/k8s-device-plugin/releases>            |
| reloader                  | kube-system        | `ghcr.io/stakater/charts/reloader`                                                                | <https://github.com/stakater/Reloader/releases>                   |
| spegel                    | kube-system        | `ghcr.io/spegel-org/helm-charts/spegel`                                                           | <https://github.com/spegel-org/spegel/releases>                   |
| cert-manager              | cert-manager       | `quay.io/jetstack/charts/cert-manager`                                                            | <https://github.com/cert-manager/cert-manager/releases>           |
| flux-operator             | flux-system        | `ghcr.io/controlplaneio-fluxcd/charts/flux-operator`                                              | <https://github.com/controlplaneio-fluxcd/flux-operator/releases> |
| flux-instance             | flux-system        | `ghcr.io/controlplaneio-fluxcd/charts/flux-instance`                                              | same repository as flux-operator                                  |
| cloudflare-dns            | network            | `ghcr.io/home-operations/charts-mirror/external-dns`                                              | <https://github.com/kubernetes-sigs/external-dns/releases>        |
| unifi-dns                 | network            | `ghcr.io/home-operations/charts-mirror/external-dns`                                              | <https://github.com/kubernetes-sigs/external-dns/releases>        |
| unifi-dns (image)         | network            | `ghcr.io/home-operations/external-dns-unifi-webhook`                                              | <https://github.com/home-operations/external-dns-unifi-webhook>   |
| cloudflare-tunnel         | network            | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| cloudflare-tunnel (image) | network            | `docker.io/cloudflare/cloudflared`                                                                | <https://github.com/cloudflare/cloudflared/releases>              |
| envoy-gateway             | network            | `mirror.gcr.io/envoyproxy/gateway-helm`                                                           | <https://github.com/envoyproxy/gateway/releases>                  |
| k8s-gateway               | network            | `codeberg.org/k8s-gateway/charts/k8s-gateway`                                                     | <https://codeberg.org/k8s-gateway/k8s_gateway>                    |
| local-path-provisioner    | storage            | `ghcr.io/rancher/local-path-provisioner/charts/local-path-provisioner`                            | <https://github.com/rancher/local-path-provisioner/releases>      |
| cloudnative-pg            | cnpg-system        | `ghcr.io/cloudnative-pg/charts/cloudnative-pg`                                                    | <https://github.com/cloudnative-pg/cloudnative-pg/releases>       |
| plugin-barman-cloud       | cnpg-system        | `ghcr.io/cloudnative-pg/charts/plugin-barman-cloud`                                               | <https://github.com/cloudnative-pg/plugin-barman-cloud/releases>  |
| kube-prometheus-stack     | observability      | `ghcr.io/prometheus-community/charts/kube-prometheus-stack`                                       | <https://github.com/prometheus-community/helm-charts/releases>    |
| influxdb                  | observability      | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| influxdb (image)          | observability      | `docker.io/library/influxdb`                                                                      | <https://github.com/influxdata/influxdb/releases>                 |
| pocket-id                 | security           | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| pocket-id (image)         | security           | `ghcr.io/pocket-id/pocket-id`                                                                     | <https://github.com/pocket-id/pocket-id/releases>                 |
| radar                     | radar              | `ghcr.io/skyhook-io/charts/radar`                                                                 | <https://github.com/skyhook-io/radar/releases>                    |
| localai                   | ai                 | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| localai (images)          | ai                 | `localai/localai` and `quay.io/go-skynet/local-ai-backends`                                       | <https://github.com/mudler/LocalAI/releases>                      |
| pegaprox                  | pegaprox           | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| pegaprox (image)          | pegaprox           | `ghcr.io/pegaprox/pegaprox`                                                                       | <https://github.com/PegaProx/project-pegaprox/releases>           |
| matherlynet               | matherlynet        | `ghcr.io/jrmatherly/matherlynet/charts/matherlynet`                                               | <https://github.com/jrmatherly/matherlynet/commits/main>          |
| network-optimizer         | network-optimizer  | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| network-optimizer (image) | network-optimizer  | `ghcr.io/ozark-connect/network-optimizer`                                                         | <https://github.com/Ozark-Connect/NetworkOptimizer/releases>      |
| actual-budget             | actual-budget      | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| actual-budget (image)     | actual-budget      | `ghcr.io/actualbudget/actual`                                                                     | <https://github.com/actualbudget/actual/releases>                 |
| ai-workspace              | ai-workspace       | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| ai-workspace (image)      | ai-workspace       | `ghcr.io/jrmatherly/ai-workspace`                                                                 | <https://github.com/jrmatherly/ai-workspace/releases>             |
| browserless (image)       | ai-workspace       | `ghcr.io/browserless/chromium` (plain Deployment, pinned by digest)                               | <https://github.com/browserless/browserless/releases>             |
| ai-kb                     | ai-kb              | `ghcr.io/jrmatherly/ai-kb/charts/ai-kb` (own chart, `OCIRepository` tag)                          | <https://github.com/jrmatherly/ai-kb/releases>                    |
| ai-kb (images)            | ai-kb              | `ghcr.io/jrmatherly/ai-kb-{app,ui,website,docreader}` (one CalVer tag, pinned by digest)          | <https://github.com/jrmatherly/ai-kb/releases>                    |
| ai-kb extension (image)   | ai-kb              | `docker.io/paradedb/paradedb-extension` (a `customManagers` rule reads this `image.reference`)    | <https://github.com/paradedb/paradedb/releases>                   |
| neo4j (image)             | ai-kb              | `neo4j` (the ai-kb chart's default tag, `2026.09.0`; not pinned here, moves with the chart)       | <https://github.com/neo4j/neo4j/releases>                         |
| searxng                   | ai-kb              | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| searxng (image)           | ai-kb              | `docker.io/searxng/searxng` (CalVer tag plus commit, pinned by digest)                            | <https://github.com/searxng/searxng/commits/master>               |
| kener                     | kener              | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| kener (image)             | kener              | `ghcr.io/rajnandan1/kener`                                                                        | <https://github.com/rajnandan1/kener/releases>                    |
| reactive-resume           | reactive-resume    | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| reactive-resume (image)   | reactive-resume    | `ghcr.io/reactive-resume/reactive-resume`                                                         | <https://github.com/AmruthPillai/Reactive-Resume/releases>        |
| media apps (9 charts)     | media              | `ghcr.io/bjw-s-labs/helm/app-template`                                                            | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| sonarr (image)            | media              | `ghcr.io/home-operations/sonarr`                                                                  | <https://github.com/Sonarr/Sonarr/releases>                       |
| radarr (image)            | media              | `ghcr.io/home-operations/radarr`                                                                  | <https://github.com/Radarr/Radarr/releases>                       |
| prowlarr (image)          | media              | `ghcr.io/home-operations/prowlarr`                                                                | <https://github.com/Prowlarr/Prowlarr/releases>                   |
| sabnzbd (image)           | media              | `ghcr.io/home-operations/sabnzbd`                                                                 | <https://github.com/sabnzbd/sabnzbd/releases>                     |
| recyclarr (image)         | media              | `ghcr.io/recyclarr/recyclarr`                                                                     | <https://github.com/recyclarr/recyclarr/releases>                 |
| bazarr (image)            | media              | `ghcr.io/home-operations/bazarr`                                                                  | <https://github.com/morpheus65535/bazarr/releases>                |
| tautulli (image)          | media              | `ghcr.io/home-operations/tautulli`                                                                | <https://github.com/Tautulli/Tautulli/releases>                   |
| seerr (image)             | media              | `ghcr.io/seerr-team/seerr`                                                                        | <https://github.com/seerr-team/seerr/releases>                    |
| maintainerr (image)       | media              | `ghcr.io/maintainerr/maintainerr`                                                                 | <https://github.com/jorenn92/Maintainerr/releases>                |
| hook jobs (image)         | media, kube-system | `docker.io/alpine/k8s` (media configure Jobs, `restart-reset`)                                    | <https://github.com/alpine-docker/k8s>                            |
| wait init (image)         | five apps          | `docker.io/library/busybox` (ai-workspace, kener, radar, reactive-resume, local-path-provisioner) | <https://hub.docker.com/_/busybox>                                |
| csi-driver-nfs            | storage            | classic `HelmRepository`, one of two; the inventory cannot see it                                 | <https://github.com/kubernetes-csi/csi-driver-nfs/releases>       |
| rustfs                    | rustfs             | classic `HelmRepository` `https://charts.rustfs.com`, one of two; the inventory cannot see it     | <https://github.com/rustfs/rustfs/releases>                       |
| rustfs (images)           | rustfs             | `ghcr.io/rustfs/rustfs`, and `docker.io/library/busybox` for the chart's init container           | <https://github.com/rustfs/rustfs/releases>                       |
| rustfs provision (image)  | rustfs             | `docker.io/rustfs/rc`                                                                             | <https://github.com/rustfs/cli/releases>                          |
| langfuse                  | langfuse           | `ghcr.io/langfuse/langfuse-k8s/charts/langfuse` (the chart lags the app; images pinned apart)     | <https://github.com/langfuse/langfuse-k8s/releases>               |
| langfuse (images)         | langfuse           | `docker.io/langfuse/langfuse` and `docker.io/langfuse/langfuse-worker` (one version, by digest)   | <https://github.com/langfuse/langfuse/releases>                   |
| clickhouse (image)        | langfuse           | `docker.io/clickhouse/clickhouse-server` (plain StatefulSet, pinned by digest; 25.12 or later)    | <https://github.com/ClickHouse/ClickHouse/releases>               |
| docs (image)              | docs               | `ghcr.io/jrmatherly/home-cluster/docs` (`:latest`, Renovate pins it)                              | this repo's Docs Image workflow                                   |
| redis (component image)   | per consumer       | `docker.io/library/redis`                                                                         | <https://github.com/redis/redis/releases>                         |
| postgres (ImageCatalog)   | per consumer       | `ghcr.io/cloudnative-pg/postgresql`                                                               | <https://github.com/cloudnative-pg/postgres-containers/releases>  |
| echo                      | default            | `ghcr.io/home-operations/charts/echo`                                                             | not identified; ask the user or search before a non-patch bump    |
| prometheus-operator-crds  | bootstrap only     | `ghcr.io/prometheus-community/charts/prometheus-operator-crds`                                    | <https://github.com/prometheus-community/helm-charts/releases>    |

The charts under `charts-mirror` are copies of the upstream chart, so the upstream project's notes apply.

## Apps that move together

- **flux-operator and flux-instance** share a version. Update both in one commit.
- **cloudflare-tunnel** has two pins: the `app-template` chart and the `cloudflared` image. They are independent.
  Update them in separate commits so a failure points at one of them.
- **langfuse web and worker** share a version and a schema, which the web pod migrates on start. Update both
  images in one commit; the chart is independent and pins neither. The ai-kb HelmRelease names the chart's web
  Service (`langfuse-web`) in `LANGFUSE_HOST`, and the HelmRelease's `postRenderers` patches find the
  `langfuse-web` and `langfuse-worker` Deployments by name (the web startup probe, and
  `enableServiceLinks: false` on both, without which the kubelet's `REDIS_PORT=tcp://...` stops Langfuse
  starting), so check those names on a chart bump. A first install waits for Ready, so a fix pushed while it
  hangs waits out the 15-minute timeout unless the Deployments are patched by hand with the same change.

## Order when several are pending

1. flux-operator with flux-instance, so the tool doing the deploying is current first.
2. cert-manager.
3. The network apps: envoy-gateway, cloudflare-dns, k8s-gateway, cloudflare-tunnel.
4. Everything else in kube-system except cilium.
5. cilium last, on its own, when nothing else is in flight.

## App-specific cautions

- **cilium** is the cluster network. A failed upgrade can cut every node off. Cross one minor version at a time
  and read the upgrade guide for the target minor at <https://docs.cilium.io/en/stable/operations/upgrade/>. This
  cluster uses kube-proxy replacement, L2 announcements and BGP, so check the notes for those three features. The
  inventory shows only the newest tag. When that is more than one minor ahead, pick the newest patch of the next
  minor from `gh release list -R cilium/cilium` and update to that first.
- **coredns** overrides the image repository to `mirror.gcr.io/coredns/coredns` and sets no tag, so the chart's
  `appVersion` decides the image. Confirm that tag exists on the mirror before updating the chart.
- **envoy-gateway** ships the Gateway API and Envoy CRDs. Follow the CRD section of `breaking-changes.md`. It
  also pulls its images through a mirror, set in two places: `global.imageRegistry` in its `helmrelease.yaml.j2`
  and `imageRepository` in `envoy.yaml.j2`. When the chart moves or renames an image, both need checking.
- **cloudflare-dns** ships the `DNSEndpoint` CRD, which the cloudflare-tunnel app uses.
- **k8s-gateway** moved to a `servers[]` layout in chart 4.0.0: the zone, port, Service port and every
  CoreDNS plugin are listed per server, and `domain`, `ttl`, `watchedResources`, `service.type` and
  `service.port` do nothing. The chart defaults to `example.com`, root, `dnsPolicy: Default` and a
  readiness probe that fails on one miss, so the HelmRelease pins `securityContext.runAsUser: 1000`,
  `deployment.dnsPolicy: ClusterFirst` and the old probe thresholds. The Corefile is the ConfigMap
  `k8s-gateway` in `network`; compare it before and after any chart bump. From image 1.9.2 (chart 4.0.1)
  it also reads `external-dns.kubernetes.io/hostname` on Services, so it answers `external.` and
  `internal.<domain>` with the Envoy gateway addresses (both were empty before, measured 2026-10-15).
- **spegel** dropped the host port in chart 0.8.0: `service.registry.hostPort` is gone, containerd's mirror
  points only at the registry NodePort (30020 since 0.8.0, 30021 before) with `trafficDistribution:
  PreferSameNode`, and the registry refuses containerd older than 2.2 at startup and, on 2.4 or later,
  `discard_unpacked_layers = true` (`talos/all/50-files.yaml` sets it false). The chart has no values
  schema, so a removed key renders without error and does nothing; diff the defaults.
- **unifi-dns** is a second ExternalDNS, with a webhook sidecar that writes local DNS records to the UniFi
  console for routes on the internal gateway. It has two pins: the `external-dns` chart, shared with
  cloudflare-dns, and the webhook image. The webhook's README lists the minimum ExternalDNS and UniFi Network
  versions: check both before updating either pin. A broken update leaves the existing records in place, so
  names keep resolving, but new routes get no record. It cannot be dry-run: ExternalDNS leaves `--dry-run` to
  each provider, and the webhook provider ignores it. Before a chart update, run the old and the new ExternalDNS
  image once each with this app's sources and `--provider=inmemory --inmemory-zone=<domain> --dry-run --once`,
  and compare the `CREATE` lines. The same record set from both means the update changes nothing on the console.
  cloudflare-dns can use a real `--dry-run --once`, which the Cloudflare provider honors.
- **nvidia-device-plugin** renders only when a node lists the `nvidia` kernel module. The driver itself comes
  from the Talos extension, not from this chart.
- **local-path-provisioner** backs every PersistentVolume in the cluster. A volume is a directory under
  `/var/mnt/local-path` on one node (the Talos user volume in `talos/all/72-volumes.yaml`), so a pod using it is
  pinned to that node and the volume has no size limit. Before updating, read the notes for a change to the path
  layout or the helper pod: either could orphan existing volumes.
- **cloudnative-pg** is the Postgres operator, and its chart ships the CNPG CRDs. An operator update restarts the
  pods of every Postgres cluster it manages, one cluster at a time with a switchover, so update it when a short
  database interruption is acceptable. Read the upgrade notes for the target version first.
- **plugin-barman-cloud** takes the Postgres backups and archives WAL. It must run in the operator's namespace,
  and it talks to the operator over mutual TLS with certificates from cert-manager. It needs operator 1.26 or
  newer, and its notes name any higher minimum: check that before updating either one. The chart also sets the
  sidecar image that runs in every backed-up Postgres pod.
- **kube-prometheus-stack** ships the Prometheus Operator CRDs and replaces them on every install and upgrade,
  so it, not the bootstrap `prometheus-operator-crds` pin, decides the CRD version on a running cluster. Follow
  the CRD section of `breaking-changes.md`, and read the chart's upgrade notes for each major version crossed:
  <https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack#upgrading-chart>.
  Grafana, kube-state-metrics and node-exporter are subcharts and move with it. Freelens draws its charts from
  the `prometheus-operated` Service, so check them after an update. Grafana's bundled datasource plugins live on
  the volume (`shadowBundledPlugins`) and update themselves at start (`preinstall_auto_update`) and every ten
  minutes (`pluginsAutoUpdate`); never list them in `preinstall`, which kills them on the distroless image.
  The GitHub dashboard in `app/dashboards/github.json` is the "GitHub Default" dashboard the
  `grafana-github-datasource` plugin bundles (`/public/plugins/grafana-github-datasource/dashboards/dashboard.json`
  on the running Grafana), with six edits: `__inputs`, `__requires` and `id` removed, `uid` set to
  `github-default`, the `${DS_GITHUB}` input replaced by the dashboard's own `${datasource}` variable, the
  `organization` and `repository` defaults set to `jrmatherly` and `home-cluster`, the Packages panel's
  `packageType` set to `DOCKER`, because the GitHub App's account publishes container images and the API rejects
  `NPM` for it, and an "Actions and Dependabot" row (a `workflow` variable, a Workflow runs table and two
  Dependabot alert panels) appended by `private/grafana-dashboards/add-actions-row.py`. The row's queries name the
  workflow as `options.workflow`, the key the plugin's backend reads; `options.workflowID`, which its frontend
  types name, makes it ask GitHub for an empty workflow and report "workflow not found". Code scanning panels are
  left out because the App's repositories have no code scanning analyses and that query errors instead of
  returning an empty frame. Refresh it from the installed plugin when a plugin release changes that file,
  reapplying those edits. The Sentry dashboard in `app/dashboards/sentry.json` is hand-written, because the Sentry plugin bundles
  none; its query shapes follow `src/types.ts` of `grafana/sentry-datasource` at the installed version.
- **influxdb** stays on 2.x: InfluxDB 3 is a different database with no Flux, and a Renovate rule holds the image
  below 3. The admin password and token are read on the first start only, so changing them in `cluster.toml`
  later changes nothing in the database. The Proxmox hosts write to it over the internal gateway.
- **pocket-id** is the identity provider, so a broken update locks every login that goes through it. Stay on the
  `-distroless` image variant. It migrates its database on start and refuses to start on a database a newer
  version migrated, so a rollback after a migration means restoring `pocket-id-db` from its backup: read the notes
  for a migration before updating, and confirm a recent backup with `kubectl -n security get backup`. Its hostname
  must never change, because passkeys are bound to it. Recovery after losing every passkey is
  `kubectl -n security exec deploy/pocket-id -- /app/pocket-id one-time-access-token <user>`.
- **radar** releases about once a week, and its chart and image share a version. It runs with its own OIDC login,
  so its ServiceAccount can read every Secret and impersonate any user: read the notes for changes to `auth`, to
  the chart's ClusterRole, and to the timeline's database migrations before updating. It does not start without
  its database (`radar-db`) and does not recover by itself after losing it, so if the UI serves errors after an
  update, check the database first and then restart the Deployment. Upstream tests Postgres 17 and this repo
  runs 18.
- **matherlynet** is the public site, built and released from `~/dev/matherlynet`. There are no GitHub releases:
  the chart's `appVersion` is the site commit it was built from, and the chart carries the web image digest, so a
  chart bump moves the image too. The expected rendered diff is two lines, the `web_image` digest and
  `SENTRY_RELEASE`; anything more is a chart change to read. Its database (`matherlynet-db`) is outside the chart.
- **localai** renders only on a cluster with an NVIDIA node, and holds the whole GPU. Its main image and backend
  image move together (Renovate group "LocalAI"); the backend tag must keep the `-gpu-nvidia-cuda-12-llama-cpp`
  suffix, because the GPU is a GTX 1080 (Pascal). The model images are hand-bumped: edit the pins in
  `images/<model>/Dockerfile` and push, the Model Images workflow builds the new tag and prints its digest in
  the run summary, then update the image volume reference and `parameters.model` in the `localai-models`
  ConfigMap. The `ai` namespace enforces the `restricted` pod security level, so a test pod there needs a full
  security context. After an update, `/readyz` answers 200 only once the models are preloaded. The embedding
  model (`images/nomic-embed-text-v1.5`) produces the 768-dimension vectors AI KB stores, so a replacement
  must keep that dimension or every knowledge base is re-embedded.
- **ai-kb** is Jason's own product (`jrmatherly/ai-kb`): the chart and its four images are released together
  under one CalVer tag, so bump the `OCIRepository` tag and the four digests in one change, and read the
  release's chart notes, because the HelmRelease passes `OIDC_AUTH_*`, `BUILTIN_MODELS_CONFIG`,
  `SSRF_WHITELIST_EXTRA`, `DISABLE_REGISTRATION`, `AIKB_IM_PLATFORMS`, `AIKB_AUDIT_RETENTION_DAYS`,
  `STORAGE_ALLOW_LIST`, `AIKB_BOOTSTRAP_SYSTEM_ADMIN_EMAIL`, `OIDC_AUTH_EXTENSION_RETURN_URLS`,
  `LOCALAI_API_KEY`, the `LANGFUSE_*` tracing settings and the `S3_*` storage settings through
  `app.extraEnv`, sets `app.env.STORAGE_TYPE` and `neo4j.enabled`, mounts the `ai-kb-models`
  ConfigMap through `app.extraVolumes` and `app.extraVolumeMounts`, and sets `externalDatabase.host` and
  `externalRedis.addr`, which chart 0.4.1 requires when its own Postgres and Redis are off; check
  each key against the new chart's `values.yaml`. Both NetworkPolicies select the chart's pods by
  `app.kubernetes.io/component` (`app`, `docreader`, and `graph` for Neo4j), so check those labels too. Its database runs one CNPG instance (the community pg_search refuses to start
  on a standby) and loads `pg_search` from `paradedb/paradedb-extension`, whose Postgres major and Debian
  release must match the catalog image in `components/postgres`; Renovate offers it through a
  `customManagers` rule, and Docker versioning keeps it on `-18-trixie` tags. The app's migrations run
  `ALTER EXTENSION pg_search UPDATE`, so the extensions must stay owned by the `app` role (the Cluster's
  initdb SQL does that on a fresh install). After an update, the app log's migration block must end with
  `Database migrated from version N to M`, not `Continuing with application startup`.
- **rustfs** released 1.0.0 to 1.0.3 in a month, and its chart and image share a version. The chart's `main`
  runs ahead of the published tarball, so read `values.yaml` from the tarball of the new version, not from Git.
  It runs standalone on one `local-path` volume, which an upgrade keeps (the chart marks the claim
  `helm.sh/resource-policy: keep`). Check the notes for scanner and single-disk memory changes
  (rustfs/rustfs#8121, #8015), which is why `scanner.cycle_secs` is set. `rc` is pre-1.0; after bumping it, run
  the provisioning Job's script against the new image, because it depends on `bucket create --ignore-existing`
  and `admin service-account info`, `create` and `update`, and check its log for a secret key: `rc` prints
  one on success, so the script sends that output to `/dev/null`.
- **pegaprox** releases about once a week and holds the Proxmox credentials. Read each release's list of
  behaviour changes before bumping. Two critical authorization advisories were fixed in 1.1.1, so never go below
  1.2.0. GitHub tags carry a `v` and image tags do not. Never automerge its updates. The Grafana dashboard in
  `app/dashboards/pegaprox-overview.json` is upstream's `misc/grafana/` JSON with only `refresh` changed from 10s to 1m to match the scrape interval, so refresh it
  when a release changes that file.
- **network-optimizer** ran pre-release tags until 2026-10-10, while the stable release's Performance Tweaks page
  refused the UDM-SE's UniFi OS; 2.9.2 carries the same cap as the last preview, so it is on the stable tag. That page caps the gateway firmware at `MaxSupportedFirmware` in
  `src/NetworkOptimizer.Web/Services/PerfTweaksDeploymentService.cs` and shows the firmware red above it, so after
  a UniFi OS update on the gateway, compare the version on that page with the constant in the pinned tag. If a
  preview pin is ever needed again (`v<semver>-preview<n>`, about daily): the inventory reads `-preview<n>` as a
  variant and then shows neither the next preview nor the stable release, so list them with
  `gh release list -R Ozark-Connect/NetworkOptimizer`; the `.renovaterc.json5` rule offers the stable release once
  it exists. Before a bump, run
  `git diff v<old>..v<new> -- docker/Dockerfile src/NetworkOptimizer.Storage/Migrations/` in a clone. The init
  container copies the image's `ping` and `traceroute.db`, and the migrations run at startup on the only copy of
  the SQLite database, so anything other than CreateTable, AddColumn and CreateIndex means Flux's rollback needs
  a backup first.
- **actual-budget (image)** tags are `<yy>.<m>.<n>` with no `v`. `-alpine` is a variant, and `edge` and `latest`
  are moving tags. Renovate's docker versioning reads the plain tag, so it needs no rule.
- **sonarr, radarr, prowlarr (images)** are home-operations builds whose tags carry the upstream build number
  (`4.0.20.3012`) and include builds upstream marks pre-release; the tag cannot show which. Before moving one,
  check `gh release view v<tag> -R Sonarr/Sonarr --json isPrerelease` (or the Radarr or Prowlarr repository).
  A pre-release build can be the same source as the stable one: upstream tags a build, then promotes a later
  build of the same commit, so compare the two before switching images
  (`gh api repos/Sonarr/Sonarr/compare/v<pin>...v<stable> --jq .status`; `identical` means nothing to gain).
  The Sonarr image publishes the v5 pre-releases and skipped the stable `4.0.20.3014`, but that tag and the
  pin `4.0.20.3012` are both commit `cab419a` (checked 2026-10-15), so keep the pin until v5 goes stable. The
  stable-tagged alternatives cost more: `hotio/sonarr` writes to `/etc` and fails on a read-only root, and
  `linuxserver/sonarr` starts under the pod's securityContext with a `/run` emptyDir but calls read-only plus
  non-root unsupported (both measured in Docker). Radarr and Prowlarr pin upstream's latest stable. A Sonarr
  v5 move also needs Recyclarr 8.8.0 or later.
- **prometheus-operator-crds** is applied once by `just bootstrap apps` and is not a Flux app. Changing its
  version in the template changes nothing on a running cluster, where kube-prometheus-stack replaces the CRDs.
  The pin only decides what a rebuild installs first, so keep it on the chart whose `appVersion` is the operator
  version kube-prometheus-stack ships. Compare the two with `helm show chart <url> --version <version>`. When
  the newest CRD chart is ahead of that operator version, leave the pin and move it with the
  kube-prometheus-stack update that catches up. An update is the edit, the render and
  `just template test-helmfile`. There is nothing to wait for or check on the cluster.
  Renovate tracks the pin through the `# renovate:` comment above it, which must stay on the line directly above
  `version:`.

## Wait for the release

`just kube reconcile` only makes Flux fetch Git. The Helm upgrade runs afterwards, so wait for it before checking
anything.

For a chart update, wait for the new version and then for readiness:

```sh
kubectl -n <namespace> wait hr/<app> --for=jsonpath='{.status.history[0].chartVersion}'=<new-version> --timeout=10m
kubectl -n <namespace> wait hr/<app> --for=condition=Ready --timeout=10m
```

For an image-only update the chart version does not change, so wait for the rollout instead:

```sh
kubectl -n <namespace> rollout status deploy/<app> --timeout=10m
```

A timeout is a failure. Go to the rollback step.

## Post-deploy checks

Run the common checks for every app, then the app's own check.

Common:

```sh
flux get hr -n <namespace> <app>          # Ready is True and the revision is the new version
kubectl -n <namespace> get pods           # all Running, no climbing restart count
flux get ks -A | grep -v True             # nothing else went unready
```

Addresses and the domain come from `cluster.toml`. Read them without printing the token:

```sh
uv run --locked --no-dev template/scripts/validate.py cluster.toml 2>/dev/null \
    | jq '{domain: .domain.name, gateways, api: .kubernetes.api.addr}'
```

| App                          | Check                                                                                                                           | Healthy result                                                   |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| cilium                       | `kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status --brief`                                            | `OK`                                                             |
| cilium                       | `kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg bgp peers`                                                 | session `established`                                            |
| cilium                       | `kubectl get nodes`                                                                                                             | every node `Ready`                                               |
| coredns                      | `kubectl run dns-check --rm -i --restart=Never --image=busybox:1.38 -- nslookup kubernetes.default.svc.cluster.local`           | an address is returned                                           |
| metrics-server               | `kubectl top nodes`                                                                                                             | a row per node                                                   |
| nvidia-device-plugin         | `kubectl get nodes -o jsonpath='{.items[*].status.allocatable.nvidia\.com/gpu}'`                                                | at least `1`                                                     |
| cert-manager                 | `kubectl get certificates -A`                                                                                                   | every certificate `True`                                         |
| flux-operator, flux-instance | `flux check`                                                                                                                    | all checks passed                                                |
| cloudflare-dns               | `kubectl -n network logs deploy/cloudflare-dns --since=5m`                                                                      | no errors, records in sync                                       |
| unifi-dns                    | `kubectl -n network logs deploy/unifi-dns -c external-dns --since=5m` and `dig +short grafana.<domain>`                         | no errors, and the internal gateway address                      |
| cloudflare-tunnel            | `curl -s -o /dev/null -w '%{http_code}' https://echo.<domain>/`                                                                 | `200`                                                            |
| envoy-gateway                | `kubectl get gateway -A`                                                                                                        | both gateways programmed, with addresses                         |
| envoy-gateway                | `nc -z <gateways.internal> 443` and `nc -z <gateways.external> 443`                                                             | both open                                                        |
| k8s-gateway                  | `dig +short echo.<domain> @<gateways.dns>`                                                                                      | the external gateway address                                     |
| local-path-provisioner       | `kubectl get storageclass local-path` and `kubectl get pvc -A`                                                                  | class exists, every claim `Bound`                                |
| cloudnative-pg               | `kubectl get clusters.postgresql.cnpg.io -A`                                                                                    | every cluster in a healthy state                                 |
| plugin-barman-cloud          | `kubectl -n cnpg-system get certificates`                                                                                       | both certificates `True`                                         |
| kube-prometheus-stack        | `kubectl -n observability get prometheus,alertmanager` and `curl -s https://grafana.<domain>/api/health`                        | both `Available`, and `"database": "ok"`                         |
| influxdb                     | `curl -s https://influxdb.<domain>/health`                                                                                      | `"status":"pass"`                                                |
| pocket-id                    | `curl -s -o /dev/null -w '%{http_code}' https://auth.<domain>/healthz`, then sign in once                                       | `204`, and the passkey sign-in works                             |
| radar                        | `curl -s -o /dev/null -w '%{http_code}' https://radar.<domain>/api/health`, then sign in once                                   | `200`, and the page shows cluster data                           |
| pegaprox                     | `curl -s https://pegaprox.<domain>/api/health`, then sign in and open a VM console and a node shell                             | `{"status":"ok",...}`, and both consoles connect                 |
| matherlynet                  | `kubectl -n matherlynet rollout status deploy/matherlynet-web-deployment`, then `curl -s https://<domain>/`                     | rollout complete, and the page has `pageswap`                    |
| network-optimizer            | `kubectl -n network-optimizer exec deploy/network-optimizer -- curl -s localhost:8042/api/health`, then open Performance Tweaks | `{"status":"healthy",...}`, and the gateway firmware shows green |
| actual-budget                | `curl -s https://budget.<domain>/health` and `kubectl -n actual-budget get pods`                                                | `{"status":"UP"}`, and the pod Running                           |
| localai                      | `kubectl -n ai exec deploy/localai -- curl -fsS localhost:8080/readyz` (curl is in the image, measured 2026-10-12)              | `200` once both models are loaded                                |
| ai-workspace                 | `kubectl -n ai-workspace get pods`, then `curl -s https://ai.<domain>/api/trpc/backend.listCapabilities`                        | migrate Job Completed, app Running, a JSON body                  |
| ai-kb                        | `kubectl -n ai-kb get pods`, then `curl -s https://ai-kb.<domain>/api/v1/auth/oidc/config` and the app log's migration block    | seven pods Running, `enabled: true`, a `Database migrated` line  |
| rustfs                       | `kubectl -n rustfs get pods,jobs` and `kubectl -n rustfs logs job/rustfs-provision`                                             | pod Running, Job Completed, a `provisioned` line per consumer    |
| langfuse                     | `kubectl -n langfuse get pods` and `kubectl -n rustfs logs job/rustfs-provision`                                                | every pod Ready, `provisioned langfuse in langfuse-events`       |
| kener                        | `curl -s https://status.<domain>/healthcheck`                                                                                   | ok                                                               |
| reactive-resume              | `curl -s -o /dev/null -w '%{http_code}' https://resume.<domain>/`                                                               | `200`                                                            |
| media stack                  | `kubectl -n media get pods,jobs`, then open each UI once                                                                        | every pod Running, every configure Job Completed                 |
| docs                         | `kubectl -n docs exec deploy/docs -- wget -qO- localhost:8080/healthz`                                                          | `ok`                                                             |
| echo                         | `curl -s -o /dev/null -w '%{http_code}' https://echo.<domain>/`                                                                 | `200`                                                            |
| reloader, spegel             | the common checks                                                                                                               | pods Running                                                     |
