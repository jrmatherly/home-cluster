---
paths:
    - "template/config/kubernetes/apps/external-secrets/**"
    - "kubernetes/apps/external-secrets/**"
    - "template/config/**/externalsecret.yaml.j2"
    - "template/config/bootstrap/onepassword.yaml.j2"
    - "template/scripts/secret_map.py"
    - "template/scripts/secrets_check.py"
---

# External Secrets and 1Password (`[onepassword]`)

Every deployment secret lives in one 1Password vault, and External Secrets Operator (ESO) reads it through a 1Password Connect server in the cluster. `cluster.toml` holds no secret, and no `*.sops.*` file is left under `kubernetes/`. The plan is `docs/superpowers/plans/2026-11-22-eso-1password-secrets.md` (gitignored). Its Tasks 1 to 10 are done: the Talos secrets bundle is the vault document `talos` (`.claude/rules/talos.md`), the Talos client config is a second document, and no `*.sops.*` file is tracked. Task 11 is not done, so `.sops.yaml`, the Flux decryption wiring and the age key still exist.

## The store

- `[onepassword].vault` gates the `external-secrets` namespace: ESO and 1Password Connect, plus `ClusterSecretStore/onepassword-connect`. The validator refuses a config without the vault (the invalid fixture `app-without-vault`), because the domain and every token are read from it.
- Removing these apps would delete every Secret an ExternalSecret owns. Two guards stand against that: the validator requires the vault, and the ESO CRDs carry `helm.sh/resource-policy: keep`.
- The namespace is the one exception to the layout in `flux-apps.md`: no `postBuild.substituteFrom`, because the store has to come up before anything that needs a secret. No ESO kind may be applied by `cluster-apps`, which applies all-or-nothing. ExternalSecrets live in app folders and the two components only.
- Connect starts from two Secrets that `just bootstrap apps` creates with `op inject` over `bootstrap/onepassword.yaml` (references only). Two ExternalSecrets with `creationPolicy: Orphan` refresh them from item `1password` without owning them (measured 2026-11-22: synced, `ownerReferences` empty). So a wrong field in that item takes Connect down on the next refresh, and only the bootstrap recipe restores it.
- Connect runs one replica on an `emptyDir`, so a recreated pod needs 1Password.com reachable before any Secret can be created or refreshed. Whether it answers from its cache while 1Password.com is unreachable is not measured (the plan's Task 12 step 4).
- ESO's docs open the Connect provider page with a deprecation notice that points to the SDK provider, and the owner chose Connect knowing this (stated in the plan, not re-read). `deletionPolicy` never fires for this provider (ESO issue 6569, stated in the plan), so do not rely on it.

## Items and fields

- `template/scripts/secret_map.py` is the list of record: one item per `cluster.toml` section, titled with hyphens (`postgres-backup`, `cilium-hubble`), each field labelled with the former field name in upper case. An item is titled after its section, not the app: `unifi` for `unifi-dns`, `cilium-hubble` for Hubble, and one `career-ops` item for three Secrets. Read `secret_map.ENTRIES` for the item and field before writing an ExternalSecret.
- Four items have no section of their own: `cloudflare-tunnel` (`ACCOUNT_TAG`, `TUNNEL_SECRET`), `flux` (`WEBHOOK_TOKEN`), `cluster` (`SECRET_DOMAIN`, a copy of `domain.name`) and `ai-workspace-env` (one field per name in `ai_workspace.env_keys`). `kener` stores its mail settings as `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURE`, `SMTP_USER` and `SMTP_PASS`.
- A flag or a non-secret field turns a section on (`<section>.enabled`, `observability.discord`, `ai_workspace.browsing`, `career_ops.claude_credential`, `cliproxyapi.ohmycpa`, `ai_kb.rustfs`, an `oidc_client_id`). Each entry's `requires` names the flag that makes its field required.
- Items are made by hand in 1Password. The seeding script and its recipe are gone, with the secrets they read from `cluster.toml`.
- `just template secrets-check` (`secrets_check.py`) reads the vault with `op` and prints item and field names only. It holds the rules the validator applied while the secrets were in `cluster.toml`: a required field that is missing, a format (`pattern`), and values that must differ (the three backup key pairs and buckets, each RustFS consumer's access key, and an AI Workspace admin not admitted by `ALLOWED_EMAILS`). It also reports a label with a space and a duplicate label, because either fails ESO's read of the whole item. The validator no longer checks any of this, so a render passes with a bad vault.
- A new secret is a row in `secret_map.py`, covered by `test_secret_map.py`. `validate.py` gets only the flag or non-secret field that turns it on.

## Writing an ExternalSecret

- The file is `externalsecret.yaml.j2` in the app folder, and a second Secret gets its own file (`oidc-externalsecret.yaml.j2`, `backup-externalsecret.yaml.j2`). An ExternalSecret's name is at most 27 characters (ESO issue 7264, stated in the plan), so Connect's two are `connect-credentials` and `connect-token`.
- Every ExternalSecret has a `target.template` listing its keys, because an extract returns every field of the item, the built-in `notesPlain` included. It extracts its own item only.
- A value owned by another item is a `data` entry (`secretKey: LOCALAI_API_KEY`, `remoteRef: {key: localai, property: API_KEY}`) beside the `dataFrom` extract, as `grafana-secret` and `ai-workspace-secret` read LocalAI's key.
- A multi-line value is a block scalar with `{{ .FIELD | trim }}`, which ends in one newline (the Grafana GitHub App key matched the sops Secret byte for byte).
- A whole document can be one `target.template` key: three Helm values documents and the CLIProxyAPI config are built that way. The config adds career-ops' client key under a Go `if ne`, so it stays out when it equals the shared key.
- The tunnel token is built with `printf` in the key order `a`, `t`, `s`, the order the old encoder wrote, because `toJson` sorts keys and would change the bytes. cloudflared did not restart at its cutover.
- An ExternalSecret with no data is invalid, so one built from an optional list sits in a guard: `ai-workspace-env` and its `envFrom` entry render only when `ai_workspace.env_keys` names a variable.
- The two shared components each hold one ExternalSecret: `postgres-backup` in `components/postgres` (nine namespaces) and `redis-auth` in `components/redis` (three).
- `cluster-secrets`, which provides `${SECRET_DOMAIN}`, comes from one `ClusterExternalSecret` in `external-secrets/onepassword-connect` (`creationPolicy: Orphan`, so deleting it never deletes a copy). It writes a copy into every namespace except `cilium-secrets`, `external-secrets`, `kube-node-lease` and `kube-public`. `bootstrap/onepassword.yaml` seeds the `flux-system` copy for a cold start. `components/sops` is gone.
- `media-shared` has `wait: true`, so it reports Ready only once both of its ExternalSecrets are, and the media apps' Kustomizations wait on it while the vault is unreachable.

## Changing a secret

- Change the field in the vault item. Nothing is rendered or pushed. Every ExternalSecret has `refreshInterval: 1h`, so the Secret follows within an hour, and Reloader restarts a pod when the bytes of a Secret it reads change.
- Two changes need more, because a Job has to run again. After a media key or the Plex token changes, raise `media.keys_revision`: the media HelmReleases are upgraded and their configure hooks push the new keys into the apps. After a RustFS consumer's pair changes, raise `rustfs.keys_revision`: the provisioning Job is recreated. Both then need `just configure` and a push. They fill the annotations the key checksums filled.
- Some values are read once by the app and need a step inside it: the app rule files say which (`cliproxyapi`, `langfuse`, `ai-kb`'s Neo4j, `pocket-id`).

## Cutover results (2026-11-22 and 2026-11-23)

The method is kept for the last sops Secrets. A cutover is two pushes. Push 1 adds `kustomize.toolkit.fluxcd.io/prune: disabled` to the sops Secret. Push 2 removes the Secret from Git and adds the ExternalSecret, and the rendered `secret.sops.yaml` needs a `git rm`, because makejinja never deletes output. Record a Secret's UID and `jsonpath='{.data}' | shasum` before push 2 and compare after. A changed hash with the same UID means the vault value differs from the live one, and Reloader restarts the app.

- The runner's Secret (`f8b0ae50`): ESO adopted the live Secret with the same UID and the same data hash, became its controlling owner, kept Flux's labels, and no pod restarted.
- The 15 leaf apps' 24 sops templates became 23 ExternalSecrets and one ConfigMap (`network-optimizer-identity`, which holds no credential). Every adopted Secret kept its UID and, compared key by key, its bytes. No pod restarted except Network Optimizer's, for the volume type change.
- `postgres-backup`: two clusters archived a new WAL file within three minutes of the cutover. The six backup Secrets and the two RustFS Secrets kept their UIDs and bytes. The last seven app Secrets (17 keys), the DNS token (two Secrets from item `dns`), the tunnel token and the Flux webhook token kept their UIDs and bytes too, and neither cloudflare-tunnel pod restarted (measured 2026-11-23).
- `cluster-secrets` moved last (`7e6af090`): all 27 copies kept their UIDs and value, with no owner reference. ESO's labels touched every copy, so every Kustomization reconciled once and nothing changed.
- Task 9 (`8d20b478`) changed the two `keys_revision` annotations once. Five media apps restarted together, and Recyclarr's configure hook failed on its first try, because Radarr restarted under it; Helm rolled back, Flux retried and it passed.
- After a push, a Kustomization with `dependsOn` reports `dependency ... is not ready` until its dependency reconciles the new revision. It cleared by itself within about two minutes.

## What Claude does not run

Claude never runs `op read`, `op inject`, `op run`, `op item get` or `op document get`, and cluster-guard refuses them. A `just` recipe that calls `op`, `just template secrets-check` included, is the owner's to run.
