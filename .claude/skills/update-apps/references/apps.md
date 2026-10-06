# Per-app notes

One row per app this repo templates. Add a row when an app is added, and add a note when an update teaches
something. Step 5 of the skill keeps this file current.

## Upstream sources

The chart column is what the template pins. The releases column is where the notes are.

| App                       | Namespace      | Chart pinned                                                           | Release notes                                                     |
| ------------------------- | -------------- | ---------------------------------------------------------------------- | ----------------------------------------------------------------- |
| cilium                    | kube-system    | `quay.io/cilium/charts/cilium`                                         | <https://github.com/cilium/cilium/releases>                       |
| coredns                   | kube-system    | `ghcr.io/coredns/charts/coredns`                                       | <https://github.com/coredns/helm/releases>                        |
| metrics-server            | kube-system    | `ghcr.io/home-operations/charts-mirror/metrics-server`                 | <https://github.com/kubernetes-sigs/metrics-server/releases>      |
| nvidia-device-plugin      | kube-system    | `ghcr.io/home-operations/charts-mirror/nvidia-device-plugin`           | <https://github.com/NVIDIA/k8s-device-plugin/releases>            |
| reloader                  | kube-system    | `ghcr.io/stakater/charts/reloader`                                     | <https://github.com/stakater/Reloader/releases>                   |
| spegel                    | kube-system    | `ghcr.io/spegel-org/helm-charts/spegel`                                | <https://github.com/spegel-org/spegel/releases>                   |
| cert-manager              | cert-manager   | `quay.io/jetstack/charts/cert-manager`                                 | <https://github.com/cert-manager/cert-manager/releases>           |
| flux-operator             | flux-system    | `ghcr.io/controlplaneio-fluxcd/charts/flux-operator`                   | <https://github.com/controlplaneio-fluxcd/flux-operator/releases> |
| flux-instance             | flux-system    | `ghcr.io/controlplaneio-fluxcd/charts/flux-instance`                   | same repository as flux-operator                                  |
| cloudflare-dns            | network        | `ghcr.io/home-operations/charts-mirror/external-dns`                   | <https://github.com/kubernetes-sigs/external-dns/releases>        |
| unifi-dns                 | network        | `ghcr.io/home-operations/charts-mirror/external-dns`                   | <https://github.com/kubernetes-sigs/external-dns/releases>        |
| unifi-dns (image)         | network        | `ghcr.io/home-operations/external-dns-unifi-webhook`                   | <https://github.com/home-operations/external-dns-unifi-webhook>   |
| cloudflare-tunnel         | network        | `ghcr.io/bjw-s-labs/helm/app-template`                                 | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| cloudflare-tunnel (image) | network        | `docker.io/cloudflare/cloudflared`                                     | <https://github.com/cloudflare/cloudflared/releases>              |
| envoy-gateway             | network        | `mirror.gcr.io/envoyproxy/gateway-helm`                                | <https://github.com/envoyproxy/gateway/releases>                  |
| k8s-gateway               | network        | `codeberg.org/k8s-gateway/charts/k8s-gateway`                          | <https://codeberg.org/k8s-gateway/k8s_gateway>                    |
| local-path-provisioner    | storage        | `ghcr.io/rancher/local-path-provisioner/charts/local-path-provisioner` | <https://github.com/rancher/local-path-provisioner/releases>      |
| cloudnative-pg            | cnpg-system    | `ghcr.io/cloudnative-pg/charts/cloudnative-pg`                         | <https://github.com/cloudnative-pg/cloudnative-pg/releases>       |
| plugin-barman-cloud       | cnpg-system    | `ghcr.io/cloudnative-pg/charts/plugin-barman-cloud`                    | <https://github.com/cloudnative-pg/plugin-barman-cloud/releases>  |
| kube-prometheus-stack     | observability  | `ghcr.io/prometheus-community/charts/kube-prometheus-stack`            | <https://github.com/prometheus-community/helm-charts/releases>    |
| influxdb                  | observability  | `ghcr.io/bjw-s-labs/helm/app-template`                                 | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| influxdb (image)          | observability  | `docker.io/library/influxdb`                                           | <https://github.com/influxdata/influxdb/releases>                 |
| pocket-id                 | security       | `ghcr.io/bjw-s-labs/helm/app-template`                                 | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| pocket-id (image)         | security       | `ghcr.io/pocket-id/pocket-id`                                          | <https://github.com/pocket-id/pocket-id/releases>                 |
| radar                     | radar          | `ghcr.io/skyhook-io/charts/radar`                                      | <https://github.com/skyhook-io/radar/releases>                    |
| llama-server              | ai             | `ghcr.io/bjw-s-labs/helm/app-template`                                 | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| llama-server (image)      | ai             | `ghcr.io/ggml-org/llama.cpp`                                           | <https://github.com/ggml-org/llama.cpp/releases>                  |
| pegaprox                  | pegaprox       | `ghcr.io/bjw-s-labs/helm/app-template`                                 | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| pegaprox (image)          | pegaprox       | `ghcr.io/pegaprox/pegaprox`                                            | <https://github.com/PegaProx/project-pegaprox/releases>           |
| matherlynet               | matherlynet    | `ghcr.io/jrmatherly/matherlynet/charts/matherlynet`                    | <https://github.com/jrmatherly/matherlynet/commits/main>          |
| echo                      | default        | `ghcr.io/home-operations/charts/echo`                                  | not identified; ask the user or search before a non-patch bump    |
| prometheus-operator-crds  | bootstrap only | `ghcr.io/prometheus-community/charts/prometheus-operator-crds`         | <https://github.com/prometheus-community/helm-charts/releases>    |

The charts under `charts-mirror` are copies of the upstream chart, so the upstream project's notes apply.

## Apps that move together

- **flux-operator and flux-instance** share a version. Update both in one commit.
- **cloudflare-tunnel** has two pins: the `app-template` chart and the `cloudflared` image. They are independent.
  Update them in separate commits so a failure points at one of them.

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
  on the running Grafana), with five edits: `__inputs`, `__requires` and `id` removed, `uid` set to
  `github-default`, the `${DS_GITHUB}` input replaced by the dashboard's own `${datasource}` variable, the
  `organization` and `repository` defaults set to `jrmatherly` and `home-cluster`, and the Packages panel's
  `packageType` set to `DOCKER`, because the GitHub App's account publishes container images and the API rejects
  `NPM` for it. Refresh it from the installed plugin when a plugin release changes that file, reapplying those
  edits. The Sentry dashboard in `app/dashboards/sentry.json` is hand-written, because the Sentry plugin bundles
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
- **llama-server** renders only on a cluster with an NVIDIA node, and holds the whole GPU. The GPU is a GTX 1080
  (Pascal), so the image must stay on a CUDA 12 build: check `CUDA_VERSION` in the new image's config before
  updating the tag. The image is pinned as `tag@sha256:digest`, so update both. The model is a second image,
  mounted as a volume and pinned by digest. Neither the inventory nor Renovate tracks it. To change the model,
  edit the pins in `images/phi-4-mini-instruct/Dockerfile` and push: the Model Images workflow builds the new tag
  and prints its digest in the run summary. Then update the reference and `LLAMA_ARG_MODEL` in the HelmRelease. The
  `ai` namespace enforces the `restricted` pod security level, so a test pod there needs a full security context. After an update, time
  one request: the pod restarts, and the startup probe's warm-up request is what keeps the first caller fast.
- **pegaprox** releases about once a week and holds the Proxmox credentials. Read each release's list of
  behaviour changes before bumping. Two critical authorization advisories were fixed in 1.1.1, so never go below
  1.2.0. GitHub tags carry a `v` and image tags do not. Never automerge its updates. The Grafana dashboard in
  `app/dashboards/pegaprox-overview.json` is upstream's `misc/grafana/` JSON with only `refresh` changed from 10s to 1m to match the scrape interval, so refresh it
  when a release changes that file.
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

| App                          | Check                                                                                                                 | Healthy result                                   |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| cilium                       | `kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status --brief`                                  | `OK`                                             |
| cilium                       | `kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg bgp peers`                                       | session `established`                            |
| cilium                       | `kubectl get nodes`                                                                                                   | every node `Ready`                               |
| coredns                      | `kubectl run dns-check --rm -i --restart=Never --image=busybox:1.38 -- nslookup kubernetes.default.svc.cluster.local` | an address is returned                           |
| metrics-server               | `kubectl top nodes`                                                                                                   | a row per node                                   |
| nvidia-device-plugin         | `kubectl get nodes -o jsonpath='{.items[*].status.allocatable.nvidia\.com/gpu}'`                                      | at least `1`                                     |
| cert-manager                 | `kubectl get certificates -A`                                                                                         | every certificate `True`                         |
| flux-operator, flux-instance | `flux check`                                                                                                          | all checks passed                                |
| cloudflare-dns               | `kubectl -n network logs deploy/cloudflare-dns --since=5m`                                                            | no errors, records in sync                       |
| unifi-dns                    | `kubectl -n network logs deploy/unifi-dns -c external-dns --since=5m` and `dig +short grafana.<domain>`               | no errors, and the internal gateway address      |
| cloudflare-tunnel            | `curl -s -o /dev/null -w '%{http_code}' https://echo.<domain>/`                                                       | `200`                                            |
| envoy-gateway                | `kubectl get gateway -A`                                                                                              | both gateways programmed, with addresses         |
| envoy-gateway                | `nc -z <gateways.internal> 443` and `nc -z <gateways.external> 443`                                                   | both open                                        |
| k8s-gateway                  | `dig +short echo.<domain> @<gateways.dns>`                                                                            | the external gateway address                     |
| local-path-provisioner       | `kubectl get storageclass local-path` and `kubectl get pvc -A`                                                        | class exists, every claim `Bound`                |
| cloudnative-pg               | `kubectl get clusters.postgresql.cnpg.io -A`                                                                          | every cluster in a healthy state                 |
| plugin-barman-cloud          | `kubectl -n cnpg-system get certificates`                                                                             | both certificates `True`                         |
| kube-prometheus-stack        | `kubectl -n observability get prometheus,alertmanager` and `curl -s https://grafana.<domain>/api/health`              | both `Available`, and `"database": "ok"`         |
| influxdb                     | `curl -s https://influxdb.<domain>/health`                                                                            | `"status":"pass"`                                |
| pocket-id                    | `curl -s -o /dev/null -w '%{http_code}' https://auth.<domain>/healthz`, then sign in once                             | `204`, and the passkey sign-in works             |
| radar                        | `curl -s -o /dev/null -w '%{http_code}' https://radar.<domain>/api/health`, then sign in once                         | `200`, and the page shows cluster data           |
| pegaprox                     | `curl -s https://pegaprox.<domain>/api/health`, then sign in and open a VM console and a node shell                   | `{"status":"ok",...}`, and both consoles connect |
| matherlynet                  | `kubectl -n matherlynet rollout status deploy/matherlynet-web-deployment`, then `curl -s https://<domain>/`           | rollout complete, and the page has `pageswap`    |
| llama-server                 | `kubectl -n ai exec deploy/llama-server -- curl -fsS localhost:8080/health`                                           | `{"status":"ok"}`                                |
| echo                         | `curl -s -o /dev/null -w '%{http_code}' https://echo.<domain>/`                                                       | `200`                                            |
| reloader, spegel             | the common checks                                                                                                     | pods Running                                     |
