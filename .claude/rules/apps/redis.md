---
paths:
    - "template/config/kubernetes/components/redis/**"
    - "kubernetes/components/redis/**"
---

# Redis (`[redis]`)

- `[redis]` in `cluster.toml` (one password of at least 24 letters and digits) gates `components/redis`, the Redis counterpart of `components/postgres`. An app that needs Redis includes the component from its `app/kustomization.yaml` and gets an instance of its own in its namespace: a `redis` StatefulSet (Redis 8, one replica, an append-only file on a 1Gi `local-path` volume, no eviction), a `redis` Service, the `redis-auth` Secret and a NetworkPolicy that admits only the same namespace. So there is at most one per namespace, at `redis:6379`. The server reads the password from a mounted `redis.conf`, so it never appears in the process arguments, and a client builds its URL from the `password` key. Instances are never shared between apps, because eviction policy, key names and blast radius differ per consumer. The `public` fixture sets the section.
