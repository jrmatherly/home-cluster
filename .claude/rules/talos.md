---
paths:
    - "template/config/talos/**"
    - "talos/**"
---

# Editing Talos config

- topf (github.com/postfinance/topf) builds each node's machine config from `topf.yaml` plus the strategic merge patches beside it. Patches merge alphabetically within each directory, in this order: `all/`, `control-plane/`, `worker/`, `node/<hostname>/`. Later patches win. The two-digit prefix on each file sets its order.
- Don't use `talosctl gen config` or `talosctl patch mc` here. Render with `just talos render`, preview with `just talos diff`, and apply with `just talos apply` or `just talos apply-node <node>`.
- A `*.yaml.tpl` file is a per-node Go template. It can read `.Node.Host`, `.Node.IP`, `.Node.Role`, and `.Node.Data.*`. The `data:` block in `topf.yaml.j2` defines the keys under `.Node.Data`: `installDisk`, `installDiskSerial`, `macAddr`, `mtu`, `encryptDisk`, and `kernelModules`. To add a per-node value, add it there and in `validate.py`'s `Node` model.
- Patches use multi-document config (`apiVersion: v1alpha1` plus a `kind`, such as `HostnameConfig` or `TimeSyncConfig`). They follow the Talos v1.14 strategic merge rules from <https://docs.siderolabs.com/talos/v1.14/configure-your-talos-cluster/system-configuration/patching>:
    - A list value is appended. `KubeNetworkConfig.podSubnets` and `serviceSubnets` are replaced. `network.interfaces` merges on `interface:` or `deviceSelector:`.
    - A document matches on `kind`, `apiVersion`, and `name`. A document with no match is appended.
    - One patch file cannot modify the same document twice.
    - `$patch: delete` removes a field or a whole document, but not the main `v1alpha1` document.
    - Use strategic merge patches, not RFC 6902 `op`/`path` patches.
- topf rejects unknown keys (`unknown keys found during decoding`), and the Stop hook runs `topf render` on the `public` fixture. Check field names against the v1.14 reference with the `siderolabs-docs` MCP. Don't use the v1.12 links in the generic `siderolabs` skill.
- The Talos and Kubernetes versions live in `topf.yaml.j2` under `# renovate:` comments. Change them only by editing those values.
- `just talos upgrade-node <node>` runs `just --yes talos drain`, then `topf upgrade --drain=false`, then `resume`, because topf's own drain skips the preflight and the CloudNativePG switchover. It asks once. `upgrade-k8s` asks first too. `resume <node> no-wait` and `uncordon <node> no-wait` skip the wait for the node's pods, because a worker's pods can need another worker on the same host still cordoned, and a chained resume then stalls until its 10-minute timeout (measured 2026-11-01). Neither the new `upgrade-node` nor `no-wait` had run on a real node as of 2026-11-01.
- The cluster PKI is the 1Password document `talos` in the vault (`secretsPath: secrets.yaml`, gitignored, never on disk between commands). `just talos topf <args>` fetches it, fails unless it has a `certs` key, runs topf and removes it on exit, and every topf call in `talos/mod.just` and `bootstrap/mod.just` goes through it. topf writes a new bundle when the file is missing, so never run bare `topf` in `talos/` against the running cluster. `just talos diff` exits 2 when it finds changes. `just configure` renders in a scratch copy with a throwaway bundle. A first bootstrap with no document stops in `just talos secrets-init` until the owner stores the generated file. Measured 2026-11-23: the stored document matched the sops bundle byte for byte, and `just talos diff` reached every node with it.
