---
paths:
    - "template/config/kubernetes/apps/kube-system/etcd-snapshot/**"
    - "kubernetes/apps/kube-system/etcd-snapshot/**"
    - "template/config/talos/control-plane/10-talos-api-access.yaml.j2"
---

# etcd snapshots (`[etcd_backup]`)

- `[etcd_backup]` in `cluster.toml` (a bucket and an S3 key pair, set all together, needing `[postgres.backup]`, whose endpoint it uses) gates `kube-system/etcd-snapshot`, a CronJob at 02:00 UTC. An init container runs `talosctl etcd snapshot` against its own node's apid, a control plane by `nodeSelector`, and the main container uploads the file to `etcd/etcd-<date>.snapshot` with `rc` and prunes objects older than 30 days. A snapshot holds every object in the cluster, so the validator refuses a bucket or access key shared with `postgres.backup`, whose pair every database namespace can read, and the R2 token is scoped to this bucket alone. The keys are limited to letters, digits, `-` and `_` (`UrlCredential`), because the job builds them into an `https://key:secret@host` URL in `RC_HOST_s3`.
- The Talos document `talos/control-plane/10-talos-api-access.yaml` grants `os:etcd:backup` to `kube-system`. It renders unconditionally, and `just talos apply` must come before the section is set, because that apply is what creates the `serviceaccounts.talos.dev` CRD and the `talos` Service the job's `ServiceAccount` and talosconfig need (measured 2026-11-01, no reboot). Talos writes the Secret `etcd-snapshot` holding that config under the key `config`.
- The prune uses `rc object find --json` with `jq`, from files and not pipes, so a failed step or a changed output shape fails the run. `--print` is a table that `xargs` would feed to `rm` word by word, and `rc find`, `rm` and `cp` are deprecated names (`rc:v0.1.36`, measured against a scratch RustFS). A 230 MiB upload fits the 256 MiB limit. The `talosctl` image tag tracks `talosVersion` in `talos/topf.yaml.j2`, and nothing ties them together, so bump it with a Talos upgrade.
- `just talos etcd-snapshot <absolute dir>` takes one by hand and refuses a relative path, because the module runs inside the repo; `.gitignore` covers `*.snapshot`. Restore steps are in `private/disaster-recovery.md`.
