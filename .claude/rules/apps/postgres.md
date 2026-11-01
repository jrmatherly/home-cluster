---
paths:
    - "template/config/kubernetes/apps/cnpg-system/**"
    - "kubernetes/apps/cnpg-system/**"
    - "template/config/kubernetes/components/postgres/**"
    - "kubernetes/components/postgres/**"
---

# Postgres (`cnpg-system`, `[postgres.backup]`)

- `cnpg-system` holds the CloudNativePG operator (`cloudnative-pg`) and its backup plugin (`plugin-barman-cloud`). The plugin must run in the operator's namespace, and its TLS certificates come from cert-manager. The namespace enforces the `restricted` pod security level.
- `[postgres.backup]` in `cluster.toml` (endpoint, bucket and an access key pair, set all together or not at all) is the object store for Postgres backups. `components/postgres` renders only when it is set. An app with a database includes that component from its `app/kustomization.yaml`, which adds the `postgres-backup` ObjectStore and Secret and the `postgresql` ImageCatalog to the app's namespace, and its `ks.yaml` depends on `cloudnative-pg` and `plugin-barman-cloud` in `cnpg-system`. Backups land under the Cluster's name in the bucket, so Cluster names must be unique across namespaces. The component also adds a `postgres` PodMonitor that scrapes every instance in the namespace, and `cnpg-system/cloudnative-pg` holds the `postgres-backup` PrometheusRule (backup failed, backup older than 36 hours, WAL archiving failing). Its rules use the plugin's `barman_cloud_cloudnative_pg_io_*` metrics, because the `cnpg_collector_*` backup metrics stay at 0 with the plugin. The component's `postgres` CiliumNetworkPolicy admits the namespace on 5432, `cnpg-system`, the other instances and the `kube-apiserver` entity on 8000 (`kubectl cnpg status` arrives as that entity, which a NetworkPolicy cannot name, and one broke it on 2026-10-31), and `observability` on 9187, so a client in another namespace needs a new rule. The `public` fixture sets the section.
