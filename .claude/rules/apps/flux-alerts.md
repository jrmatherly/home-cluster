---
paths:
    - "template/config/kubernetes/apps/flux-system/**"
    - "kubernetes/apps/flux-system/**"
---

# Flux alerts

- `flux-system/flux-operator` holds the `flux` PrometheusRule, whose `FluxHelmReleaseNotReady` and `FluxKustomizationNotReady` alerts page Discord when a HelmRelease or Kustomization that is not suspended reports Ready False for 15 minutes, which catches an upgrade Flux rolled back but not a crashing Deployment under a Kustomization with `wait: false`, which kube-prometheus-stack's `KubePodCrashLooping` covers instead (stated, helm-controller spec).
