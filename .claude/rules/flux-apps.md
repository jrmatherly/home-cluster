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
- `wait: false` is the default. Two apps set `wait: true` (`flux-operator`, `cloudflare-dns`), and `cert-manager` uses `healthChecks`. Use `dependsOn` only for a real ordering need. `flux-instance` depending on `flux-operator` is the one case today.
- `apps/<namespace>/<app>/app/` holds a `kustomization.yaml` that lists `helmrelease.yaml`, `ocirepository.yaml`, and any extra manifests. The `HelmRelease` uses `chartRef: {kind: OCIRepository, name: <app>}`, and the `OCIRepository` pins the chart with `ref.tag`.
- Renovate updates chart tags and images in these files without annotations, because the `home-operations/renovate-presets` default extends the flux, kubernetes, and helm-values managers to `.yaml.j2`. Don't add `# renovate:` comments here.
- A Secret goes in `secret.sops.yaml`. sops encrypts only `data` and `stringData`, per the `.sops.yaml` creation rules, so keep the keys readable. Never commit a decrypted secret.
- Validation runs kubeconform in strict mode against the home-operations schemas (`template/resources/kubeconform.sh`, which skips Gateway, HTTPRoute, and Secret). CI also runs `flate test all -p ./kubernetes/flux/cluster`. During the template stage, the Stop hook runs kubeconform on the `public` fixture.
- Once the cluster is running, Flux applies these files. Don't `kubectl apply` them by hand, because `kubectl apply` and `kubectl delete` prompt for confirmation. Use `just kube reconcile` to make Flux pull now.
