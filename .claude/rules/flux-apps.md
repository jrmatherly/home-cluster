---
paths:
    - "template/config/kubernetes/**"
    - "kubernetes/**"
---

# Adding or changing a Flux app

Flux reconciles `kubernetes/` from Git. During the template stage, edit the `.j2` sources under `template/config/kubernetes/`. After `just template tidy`, edit `kubernetes/` directly. The layout is the same in both.

- `apps/<namespace>/kustomization.yaml` sets `namespace:`, includes the `../../components/sops` component, and lists `./namespace.yaml` plus each app's `./<app>/ks.yaml`. A new app is not deployed until it is listed there.
- `apps/<namespace>/<app>/ks.yaml` is a Flux `Kustomization`. Every existing app uses these settings, so copy them from `apps/default/echo/ks.yaml.j2`:
    - `path: ./kubernetes/apps/<namespace>/<app>/app`
    - `interval: 1h`
    - `prune: true`
    - `targetNamespace: <namespace>`
    - `sourceRef` set to the `flux-system` GitRepository
    - `postBuild.substituteFrom` set to the `cluster-secrets` Secret, which provides `${SECRET_DOMAIN}` and the other cluster values
- `wait: false` is the default. Six apps set `wait: true` (`flux-operator`, `cloudflare-dns`, `cloudnative-pg`, `plugin-barman-cloud`, `csi-driver-nfs`, `media-shared`), and `cert-manager` uses `healthChecks`. Use `dependsOn` only for a real ordering need: `flux-instance` depends on `flux-operator`, and an app with a Postgres database depends on `cloudnative-pg` and `plugin-barman-cloud` (both in `cnpg-system`), because its manifests use their CRDs.
- `apps/<namespace>/<app>/app/` holds a `kustomization.yaml` that lists `helmrelease.yaml`, `ocirepository.yaml`, and any extra manifests. The `HelmRelease` uses `chartRef: {kind: OCIRepository, name: <app>}`, and the `OCIRepository` pins the chart with `ref.tag`. When upstream publishes no OCI chart, a `helmrepository.yaml` holds a `HelmRepository` instead and the `HelmRelease` pins the chart with `spec.chart.spec.version`.
- Renovate updates chart tags and images in these files without annotations, because the `home-operations/renovate-presets` default extends the flux, kubernetes, and helm-values managers to `.yaml.j2`. Don't add `# renovate:` comments here.
- Metrics. kube-prometheus-stack's Prometheus selects every ServiceMonitor and PodMonitor in the cluster. An app on app-template declares its scrape in the HelmRelease's `serviceMonitor` values, which render the ServiceMonitor with the chart's own selector labels; a standalone monitor file is for targets the chart does not render, such as `components/postgres/podmonitor.yaml.j2`. An app with a NetworkPolicy admits the `observability` namespace on the metrics port only, as `pegaprox` does. A Grafana dashboard ships as a `configMapGenerator` entry in the app's `kustomization.yaml`, with the JSON under `app/dashboards/` as a verbatim upstream copy, `disableNameSuffixHash: true` and the label `grafana_dashboard: "1"`; the chart's Grafana sidecar watches that label in every namespace. A scrape credential goes in its own sops Secret and is referenced from the endpoint's `authorization.credentials`.
- A Secret goes in `secret.sops.yaml`. sops encrypts only `data` and `stringData`, per the `.sops.yaml` creation rules, so keep the keys readable. Put one Secret in each sops file: sops signs the whole file with one MAC, and Flux decrypts each Secret on its own, so a second document in the file makes both fail with `MAC mismatch`. A second Secret gets its own file, as `alertmanager-secret.sops.yaml` does. Never commit a decrypted secret.
- Validation runs kubeconform in strict mode against the home-operations schemas (`template/resources/kubeconform.sh`, which skips Gateway, HTTPRoute, and Secret). CI also runs `flate test all -p ./kubernetes/flux/cluster`. During the template stage, the Stop hook runs kubeconform on the `public` fixture.
- A binary with a file capability (`getcap` shows `cap_net_raw+ep` on Debian's `ping` and `traceroute.db`) cannot even start under the `restricted` level, because the container drops every capability and the kernel refuses to exec a file whose effective capabilities it cannot grant. Copy it in an init container (`cp` drops the capability) into an emptyDir and mount the copy over the original with `subPath`, as `kener` and `network-optimizer` do. The copy then opens an unprivileged ICMP socket, which `net.ipv4.ping_group_range` allows. The nodes set it to `0 2147483647`; `network-optimizer` also pins it in `defaultPodOptions.securityContext.sysctls`, which `restricted` permits. A .NET app's `Ping` class shells out to `/bin/ping4` when it has no raw socket, so the copy fixes that path as well. Both were measured on the real images in Docker.
- Once the cluster is running, Flux applies these files. Don't `kubectl apply` them by hand, because `kubectl apply` and `kubectl delete` prompt for confirmation. Use `just kube reconcile` to make Flux pull now.
