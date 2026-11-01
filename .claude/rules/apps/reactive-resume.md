---
paths:
    - "template/config/kubernetes/apps/reactive-resume/**"
    - "kubernetes/apps/reactive-resume/**"
---

# Reactive Resume (`[reactive_resume]`)

- `[reactive_resume]` in `cluster.toml` (an auth secret and an encryption secret, each of at least 32 characters, the ID and secret of an OIDC client created by hand in Pocket ID, and an S3 endpoint, bucket and key pair, set all together, needing `[pocket_id]` and an ingress mode other than `none`) gates the `reactive-resume` namespace, which enforces the `restricted` pod security level. `reactive-resume/reactive-resume` is Reactive Resume v6, a resume builder, on the app-template chart at `resume.${SECRET_DOMAIN}` on the external gateway. Pocket ID is its only login (`FLAG_DISABLE_EMAIL_AUTH`), and a first Pocket ID sign-in creates the account. Uploads go to the S3 bucket, which must exist first; the endpoint is in the sops Secret because it holds the Cloudflare account ID. Its data is in the CloudNativePG cluster `reactive-resume-db` (two instances, WAL archiving and a daily backup at 04:00). `TRUSTED_PROXIES` is the pod CIDR, so the app reads the client address from `X-Forwarded-For`, and a NetworkPolicy admits only the `network` namespace for that reason. Its probes request `/`, not `/api/health`, because that check writes to the bucket inside a fixed 1.5 s limit and a slow bucket would take the only pod out of the Service; an init container holds the app back until the database accepts connections. Never change `auth_secret` (signs everyone out, breaks two-factor secrets) or `encryption_secret` (saved AI keys become unreadable). The `public` fixture sets the section.
