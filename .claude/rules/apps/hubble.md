---
paths:
    - "template/config/kubernetes/apps/kube-system/cilium/**"
    - "kubernetes/apps/kube-system/cilium/**"
---

# Hubble (`[cilium.hubble]`)

- `[cilium.hubble]` in `cluster.toml` (the ID and secret of an OIDC client created by hand in Pocket ID, set together, needing `[pocket_id]`) turns on Hubble, its relay and its UI in the Cilium release, with the UI at `hubble.${SECRET_DOMAIN}` on the internal gateway. Hubble UI has no login, so an Envoy Gateway `SecurityPolicy` on its route signs users in with Pocket ID, then verifies the ID token from a cookie, with `audiences` set to this client's ID so a token Pocket ID minted for another app is refused, and admits only the `cluster_admins` group. Hubble's certificates use the chart's `cronJob` method, because the default `helm` method keeps the certificates it finds and they would expire after a year. Turning the section on or off restarts the Cilium agent on every node. The `public` fixture sets the section.
