---
paths:
    - "template/config/kubernetes/apps/network/**"
    - "kubernetes/apps/network/**"
    - "template/config/kubernetes/apps/kube-system/coredns/**"
    - "kubernetes/apps/kube-system/coredns/**"
---

# Gateway path (`network`, CoreDNS)

- The `network` namespace enforces `baseline`, with `warn` and `audit` at `restricted`, because `k8s-gateway` and `unifi-dns` fail `restricted` (capabilities and privilege escalation, plus `runAsNonRoot` and seccomp on `k8s-gateway`; server dry runs, 2026-10-31).
- With more than one node, `cloudflare-tunnel` runs two `cloudflared` replicas with preferred anti-affinity on the hostname, so a restart no longer drops the public path. It has no PodDisruptionBudget. Both pods export `cloudflared_tunnel_ha_connections` (read 2026-11-01).
- With more than one node, `envoy.yaml` sets `envoyPDB` `minAvailable: 1` and preferred anti-affinity on the Envoy pods. Preferred, so a node loss never leaves a gateway pod Pending. The selector spans both gateways, because they share one EnvoyProxy and it cannot name one of them.
- With more than one control plane, CoreDNS has a PodDisruptionBudget of `maxUnavailable: 1`.
