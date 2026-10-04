# Per-app notes

One row per app this repo templates. Add a row when an app is added, and add a note when an update teaches
something. Step 5 of the skill keeps this file current.

## Upstream sources

The chart column is what the template pins. The releases column is where the notes are.

| App                       | Namespace      | Chart pinned                                                   | Release notes                                                     |
| ------------------------- | -------------- | -------------------------------------------------------------- | ----------------------------------------------------------------- |
| cilium                    | kube-system    | `quay.io/cilium/charts/cilium`                                 | <https://github.com/cilium/cilium/releases>                       |
| coredns                   | kube-system    | `ghcr.io/coredns/charts/coredns`                               | <https://github.com/coredns/helm/releases>                        |
| metrics-server            | kube-system    | `ghcr.io/home-operations/charts-mirror/metrics-server`         | <https://github.com/kubernetes-sigs/metrics-server/releases>      |
| nvidia-device-plugin      | kube-system    | `ghcr.io/home-operations/charts-mirror/nvidia-device-plugin`   | <https://github.com/NVIDIA/k8s-device-plugin/releases>            |
| reloader                  | kube-system    | `ghcr.io/stakater/charts/reloader`                             | <https://github.com/stakater/Reloader/releases>                   |
| spegel                    | kube-system    | `ghcr.io/spegel-org/helm-charts/spegel`                        | <https://github.com/spegel-org/spegel/releases>                   |
| cert-manager              | cert-manager   | `quay.io/jetstack/charts/cert-manager`                         | <https://github.com/cert-manager/cert-manager/releases>           |
| flux-operator             | flux-system    | `ghcr.io/controlplaneio-fluxcd/charts/flux-operator`           | <https://github.com/controlplaneio-fluxcd/flux-operator/releases> |
| flux-instance             | flux-system    | `ghcr.io/controlplaneio-fluxcd/charts/flux-instance`           | same repository as flux-operator                                  |
| cloudflare-dns            | network        | `ghcr.io/home-operations/charts-mirror/external-dns`           | <https://github.com/kubernetes-sigs/external-dns/releases>        |
| cloudflare-tunnel         | network        | `ghcr.io/bjw-s-labs/helm/app-template`                         | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| cloudflare-tunnel (image) | network        | `docker.io/cloudflare/cloudflared`                             | <https://github.com/cloudflare/cloudflared/releases>              |
| envoy-gateway             | network        | `mirror.gcr.io/envoyproxy/gateway-helm`                        | <https://github.com/envoyproxy/gateway/releases>                  |
| k8s-gateway               | network        | `codeberg.org/k8s-gateway/charts/k8s-gateway`                  | <https://codeberg.org/k8s-gateway/k8s_gateway>                    |
| llama-server              | ai             | `ghcr.io/bjw-s-labs/helm/app-template`                         | <https://github.com/bjw-s-labs/helm-charts/releases>              |
| llama-server (image)      | ai             | `ghcr.io/ggml-org/llama.cpp`                                   | <https://github.com/ggml-org/llama.cpp/releases>                  |
| echo                      | default        | `ghcr.io/home-operations/charts/echo`                          | not identified; ask the user or search before a non-patch bump    |
| prometheus-operator-crds  | bootstrap only | `ghcr.io/prometheus-community/charts/prometheus-operator-crds` | <https://github.com/prometheus-community/helm-charts/releases>    |

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
- **nvidia-device-plugin** renders only when a node lists the `nvidia` kernel module. The driver itself comes
  from the Talos extension, not from this chart.
- **llama-server** renders only on a cluster with an NVIDIA node, and holds the whole GPU. The GPU is a GTX 1080
  (Pascal), so the image must stay on a CUDA 12 build: check `CUDA_VERSION` in the new image's config before
  updating the tag. The inventory cannot read the image's `server-cuda-v*` tags: it reports `?` and exits
  non-zero, so check <https://github.com/ggml-org/llama.cpp/releases> by hand. The model file is pinned by commit
  and sha256 in the init container's command, and the inventory does not track it either.
- **prometheus-operator-crds** is applied once by `just bootstrap apps` and is not a Flux app. Changing its
  version in the template changes nothing on a running cluster. Applying it needs the CRD step of the bootstrap
  run by hand, which is the user's decision. Report the pending version and stop.

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

| App                          | Check                                                                                                                 | Healthy result                           |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| cilium                       | `kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status --brief`                                  | `OK`                                     |
| cilium                       | `kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg bgp peers`                                       | session `established`                    |
| cilium                       | `kubectl get nodes`                                                                                                   | every node `Ready`                       |
| coredns                      | `kubectl run dns-check --rm -i --restart=Never --image=busybox:1.37 -- nslookup kubernetes.default.svc.cluster.local` | an address is returned                   |
| metrics-server               | `kubectl top nodes`                                                                                                   | a row per node                           |
| nvidia-device-plugin         | `kubectl get nodes -o jsonpath='{.items[*].status.allocatable.nvidia\.com/gpu}'`                                      | at least `1`                             |
| cert-manager                 | `kubectl get certificates -A`                                                                                         | every certificate `True`                 |
| flux-operator, flux-instance | `flux check`                                                                                                          | all checks passed                        |
| cloudflare-dns               | `kubectl -n network logs deploy/cloudflare-dns --since=5m`                                                            | no errors, records in sync               |
| cloudflare-tunnel            | `curl -s -o /dev/null -w '%{http_code}' https://echo.<domain>/`                                                       | `200`                                    |
| envoy-gateway                | `kubectl get gateway -A`                                                                                              | both gateways programmed, with addresses |
| envoy-gateway                | `nc -z <gateways.internal> 443` and `nc -z <gateways.external> 443`                                                   | both open                                |
| k8s-gateway                  | `dig +short echo.<domain> @<gateways.dns>`                                                                            | the external gateway address             |
| llama-server                 | `kubectl -n ai exec deploy/llama-server -- curl -fsS localhost:8080/health`                                           | `{"status":"ok"}`                        |
| echo                         | `curl -s -o /dev/null -w '%{http_code}' https://echo.<domain>/`                                                       | `200`                                    |
| reloader, spegel             | the common checks                                                                                                     | pods Running                             |
