---
paths:
    - "template/config/kubernetes/apps/flux-system/**"
    - "kubernetes/apps/flux-system/**"
---

# Flux alerts

- `flux-system/flux-operator` holds the `flux` PrometheusRule. `FluxHelmReleaseNotReady` pages Discord when a HelmRelease that is not suspended reports Ready False for 15 minutes, which catches an upgrade Flux rolled back but not a crashing Deployment under a Kustomization with `wait: false`, which kube-prometheus-stack's `KubePodCrashLooping` covers instead (stated, helm-controller spec). `FluxKustomizationNotReady` waits 30 minutes, because a Kustomization retries on its own interval and a 40-minute self-healing `ReconciliationFailed` paged as critical during the 2026-10-30 power outage. `FluxSourceNotReady` covers a GitRepository, OCIRepository or HelmRepository, also at 30 minutes: a failed source keeps serving its last artifact, so its consumers stay Ready while commits stop reaching the cluster, and a source flaps not Ready for seconds during a normal reconcile.
- `flux-system`'s pod security label comes from a Namespace patch in `flux-instance`'s HelmRelease, not from `namespace.yaml`; `flux-apps.md` says why.
