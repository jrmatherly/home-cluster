---
paths:
    - "template/config/kubernetes/apps/radar/**"
    - "kubernetes/apps/radar/**"
---

# Radar (`[radar]`)

- `[radar]` in `cluster.toml` (the ID and secret of an OIDC client created by hand in Pocket ID, set together or not at all, and needing `[pocket_id]`) gates the `radar` namespace, which enforces the `restricted` pod security level. `radar/radar` is Radar, a Kubernetes UI, from its own chart at `radar.${SECRET_DOMAIN}` on the internal gateway. It signs users in with Pocket ID itself (`auth.mode: oidc`) and acts as the signed-in user through impersonation, so its ServiceAccount can read every Secret and impersonate anyone: treat the pod as cluster-admin, which is why a NetworkPolicy admits only the `network` namespace on 9280 (`radar-db` is covered by the Postgres component's policy). What a user may do comes from `clusterrolebinding.yaml`, which binds the Pocket ID group `cluster_admins` (as `oidc:cluster_admins`) to `cluster-admin`. Its timeline is in the CloudNativePG cluster `radar-db` (two instances, no backup). The `public` fixture sets the section.
