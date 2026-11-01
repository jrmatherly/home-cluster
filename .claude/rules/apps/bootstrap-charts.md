---
paths:
    - "template/config/bootstrap/**"
    - "bootstrap/**"
---

# Bootstrap charts

- The six charts `just bootstrap apps` installs (cilium, coredns, spegel, cert-manager, flux-operator, flux-instance) keep a `helm` field manager on their objects, and helm-controller's server-side apply never prunes a field another manager owns, so a key a chart later drops stays live (cilium-config kept `envoy-xds-mode: ads` after 1.20.4 on 2026-10-24, measured). `.claude/skills/update-apps/scripts/bootstrap-drift.sh` lists such fields and `--apply` releases them.
