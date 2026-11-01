---
paths:
    - "template/config/kubernetes/apps/kener/**"
    - "kubernetes/apps/kener/**"
---

# Kener (`[kener]`)

- `[kener]` in `cluster.toml` (a secret key of at least 32 characters, needing `[postgres.backup]`, `[redis]` and an ingress mode other than `none`) gates the `kener` namespace, which enforces the `restricted` pod security level. `kener/kener` is Kener, a status page with uptime monitoring, on the app-template chart at `status.${SECRET_DOMAIN}`. The internal gateway serves all of it. The external gateway serves the status page and answers 404 for `/manage`, `/account` and `/api` through an Envoy Gateway `HTTPRouteFilter`, because the first visitor to a new instance creates the admin account, the sign-in form has no rate limit, and an admin can point a monitor at any address. Its job queue is the namespace's Redis from `components/redis`. Kener keeps its check schedule there and only writes it at startup, so if Redis ever comes back empty every check stops while `/healthcheck` still answers ok, and Kener needs a restart. An init container copies the image's ping, which drops its `NET_RAW` file capability, and the copy is mounted over the original, because the original cannot start under `restricted` and every ping monitor would fail. Its data is in the CloudNativePG cluster `kener-db` (two instances, WAL archiving and a daily backup at 04:30). Single sign-on is set up in Kener's admin UI and stored in its database, not in this repo. The optional `smtp_url` and `mail_from` pair is split into the `SMTP_*` settings Kener reads (`kener_smtp`), all in the sops Secret. The `public` fixture sets the section.
