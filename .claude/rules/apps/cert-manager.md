---
paths:
    - "template/config/kubernetes/apps/cert-manager/**"
    - "kubernetes/apps/cert-manager/**"
---

# cert-manager alerts

- `cert-manager/cert-manager` holds the `cert-manager` PrometheusRule, rendered when `observability_enabled`. `CertificateNotReady` is critical after an hour of `certmanager_certificate_ready_status{condition="False"}`. `CertificateRenewalLate` is critical when `time()` has been over six hours past `certmanager_certificate_renewal_timestamp_seconds` for an hour, which leaves the wildcard about 47 hours. A threshold on time to expiry would fire on every healthy cycle, because the 160-hour certificate renews with 53 hours left. Their labels are `exported_namespace` and `name`. `CertificateRenewalLate` had not yet been read across a real renewal on 2026-11-02; the first falls about 2026-11-03.
