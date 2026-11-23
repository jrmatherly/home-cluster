---
paths:
    - "template/config/kubernetes/apps/external-secrets/**"
    - "kubernetes/apps/external-secrets/**"
    - "template/config/**/externalsecret.yaml.j2"
    - "template/config/bootstrap/onepassword.yaml.j2"
    - "template/scripts/secret_map.py"
    - "template/scripts/secrets_check.py"
    - "template/scripts/op_seed.py"
---

# External Secrets and 1Password (`[onepassword]`)

A migration in progress: `docs/superpowers/plans/2026-11-22-eso-1password-secrets.md` (gitignored) moves every secret from `cluster.toml` and sops to 1Password. Until its Task 9, secret values are still in `cluster.toml` as well, and apps not yet cut over still read sops Secrets.

- `[onepassword].vault` gates the `external-secrets` namespace: External Secrets Operator and 1Password Connect (one replica, `emptyDir`), plus `ClusterSecretStore/onepassword-connect`. The validator refuses a config that enables any app without the vault, because removing these apps deletes every Secret an ExternalSecret owns. The ESO CRDs carry `helm.sh/resource-policy: keep` for the same reason.
- The namespace is the one exception to the layout in `flux-apps.md`: no `components/sops` and no `postBuild.substituteFrom`, because the store has to come up before anything that needs a secret. No ESO kind may be applied by `cluster-apps`, which applies all-or-nothing; ExternalSecrets live in app folders only.
- Connect starts from two Secrets that `just bootstrap apps` creates with `op inject` over `bootstrap/onepassword.yaml` (references only). Two ExternalSecrets with `creationPolicy: Orphan` refresh them from item `1password` without owning them (measured 2026-11-22: synced, `ownerReferences` empty). An ExternalSecret's name is at most 27 characters, so those two are `connect-credentials` and `connect-token`.
- Items and fields come from `template/scripts/secret_map.py`: one item per `cluster.toml` section, titled with hyphens (`postgres-backup`, `cilium-hubble`), each field labelled with the field name in upper case. `just template secrets-seed` creates missing items (`--dry-run` lists and checks them offline) and never updates one that exists. `just template secrets-check` reads the vault and prints item and field names only.
- Every ExternalSecret has a `target.template` listing its keys, because an extract returns every field of the item, the built-in `notesPlain` included. It extracts its own item only; a value from another item is an explicit `data` entry.
- A cutover is two pushes. Push 1 adds `kustomize.toolkit.fluxcd.io/prune: disabled` to the sops Secret. Push 2 removes the Secret from Git and adds the ExternalSecret; the rendered `secret.sops.yaml` needs a `git rm`, because makejinja never deletes output. Measured on the runner's Secret on 2026-11-22 (`f8b0ae50`): ESO adopted the live Secret with the same UID and the same data hash, became its controlling owner, kept Flux's labels, and no pod restarted. Record a Secret's UID and `jsonpath='{.data}' | shasum` before push 2 and compare after; a changed hash with the same UID means the vault value differs from the live one, and Reloader restarts the app.
- The plan's Task 6 finished on 2026-11-22: the 15 leaf apps' 24 sops templates became 23 ExternalSecrets and one ConfigMap (`network-optimizer-identity`, which holds no credential). Every adopted Secret kept its UID and, compared key by key, its bytes, and no pod restarted except Network Optimizer's for the volume type change. Task 7 began the same night with the two shared components: `postgres-backup` in nine namespaces (two clusters archived a new WAL file within three minutes of the cutover) and `redis-auth` in three, each one ExternalSecret in its component. The six backup Secrets and the two RustFS Secrets followed on 2026-11-23, with the same UIDs and bytes. 15 sops templates remain: seven for Task 7 step 6, five for Task 8, two for Task 10 and `.sops.yaml.j2` for Task 11.
- An item is titled after its `cluster.toml` section, not the app: `unifi` for `unifi-dns`, `cilium-hubble` for Hubble, and one `career-ops` item for three Secrets. Read `secret_map.ENTRIES` for the item and field before writing an ExternalSecret.
- A value owned by another item is a `data` entry (`secretKey: LOCALAI_API_KEY`, `remoteRef: {key: localai, property: API_KEY}`) beside the `dataFrom` extract, as `grafana-secret` and `ai-workspace-secret` read LocalAI's key. A multi-line value the sops template trimmed is a block scalar with `{{ .FIELD | trim }}`, which ends in one newline as before (the Grafana GitHub App key matched byte for byte).
- An ExternalSecret with no data is invalid, so one built from an optional map sits in a guard: `ai-workspace-env` and its `envFrom` entry render only when `[ai_workspace.env]` has a key, and `secrets-seed` creates no item for an empty map, so the first key needs the item made by hand.
- `media-shared` has `wait: true`, so it reports Ready only once both of its ExternalSecrets are, and the media apps' Kustomizations wait on it while the vault is unreachable.
- After a push, a Kustomization with `dependsOn` reports `dependency ... is not ready` until its dependency reconciles the new revision. It cleared by itself within about two minutes on 2026-11-22.
- Claude never runs `op read`, `op inject`, `op run`, `op item get` or `op document get`; cluster-guard refuses them. A `just` recipe that calls `op` is the owner's to run.
