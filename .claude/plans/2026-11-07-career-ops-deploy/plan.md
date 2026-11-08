# career-ops and publish on the home cluster (PR-19) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `career.${SECRET_DOMAIN}` serves the career-ops dashboard behind Pocket ID and `cv.${SECRET_DOMAIN}` serves the publish service's share pages, both from `ghcr.io/jrmatherly` images, the house way.

**Architecture:** One new Flux namespace `career-ops` with two apps on bjw-s app-template 5.3.0: `career-ops` (web + in-pod scheduler, one replica, `/data` on a retained `local-path` claim, a `*/15` CronJob that POSTs `/api/scheduler`) and `publish` (one replica, SQLite on a retained claim). A `[career_ops]` section in `cluster.toml` gates everything; a volume-backup CronJob per app tars its claim to the `[volume_backup]` bucket nightly.

**Tech Stack:** makejinja templates (`#{ }#`, `#% %#`), pydantic validator, Flux Kustomization + HelmRelease, Envoy Gateway HTTPRoute + SecurityPolicy, sops Secrets.

**Spec:** `~/dev/career-ops/docs/superpowers/plans/2026-11-06-reactive-resume-convergence.md`, section "Deploy career-ops and the publish service to the home cluster (PR-19)", with the owner brief `~/dev/career-ops/docs/superpowers/research/2026-11-06-reactive-resume-convergence/pr-19-owner-brief.md` (its CORRECTIONS override the spec).

## Global Constraints

- Edit `.j2` sources under `template/config/` only. Never write into `bootstrap/`, `kubernetes/` or `talos/` (cluster-guard refuses it). Never commit a decrypted secret, `cluster.toml`, or a scratch config.
- Templates render oxfmt-clean at 2-space indent; `#% %#` tags on their own line.
- Mirror `reactive-resume/` for the app layout, `media/shared/app/securitypolicy.yaml.j2` for the SecurityPolicy, `pegaprox/pegaprox/app/backup-*` for the volume-backup CronJob.
- Images (digests read with `crane digest`, 2026-11-07 23:50Z):
    - `ghcr.io/jrmatherly/career-ops-server:latest@sha256:4dfeffb94f3f6606f19072e3b461d1fd639c397ad07358c8286452d88928b2e1` (uid 1000, port 3000, `HOME=/home/app`, `CAREER_OPS_CLI=claude`, GNU tar from the jammy base).
    - `ghcr.io/jrmatherly/career-ops-publish:latest@sha256:9a9ccfbadb1b4b1f66d0071540b51db56312be5230bb86970d9b6d88382cbff2` (uid 1000, port 8080, Node 24.22.2, `PUBLISH_BIND=0.0.0.0`, `PUBLISH_DB=/data/publish.db`).
- Pod CIDR is `#{ kubernetes.pod_cidr }#`. Pocket ID issuer is `https://auth.${SECRET_DOMAIN}`.
- Conventional Commits with scope `career-ops`.

## Decisions settled before the plan (see `decisions.tsv`)

| Question              | Decision                                                                                                                                                                                                                                       | Why                                                                                                                                                                                                                                                                                                                                                            |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Probe and tick `Host` | Both send `Host: localhost`; `CAREER_OPS_WEB_ALLOWED_HOSTS=career.${SECRET_DOMAIN}` only                                                                                                                                                       | `isLoopbackHost` in `origin-guard.mjs` admits `localhost` unconditionally; no extra host name needed. The public hostname is still needed so `bind-host.mjs` binds `0.0.0.0`.                                                                                                                                                                                  |
| Service name          | HelmRelease `career-ops`, controller `web`, `service.app.forceRename: career-ops-web`                                                                                                                                                          | app-template names a lone object after the release (`_determineResourceNameFromValues.tpl`); the spec's `career-ops-web.career-ops.svc` needs the rename.                                                                                                                                                                                                      |
| Route                 | Standalone `httproute.yaml.j2` (as `pegaprox`), `timeouts.request: 900s`                                                                                                                                                                       | A standalone route carries the SecurityPolicy `targetRefs` name and the `public` second parentRef cleanly.                                                                                                                                                                                                                                                     |
| Publish proxy trust   | `PUBLISH_TRUSTED_PROXIES` = pod CIDR, `PUBLISH_CLIENT_IP_HEADER=x-forwarded-for`, as the spec says                                                                                                                                             | `cv.${SECRET_DOMAIN}` reaches the pod through `cloudflared` (in `network`) then `envoy-external`, whose ClientTrafficPolicy trusts XFF from the pod CIDR. Today `server.mjs` matches `trustedProxies` by exact peer address, so the CIDR never matches and every visitor keys as the Envoy pod address (safe, degraded). Follow-up in career-ops: match CIDRs. |
| `[career_ops]` fields | `oidc_client_id`, `oidc_client_secret`, `claude_oauth_token`, `publish_secret`, `publish_auth_secret`, `publish_oidc_client_id`, `publish_oidc_client_secret`, `publish_allowed_emails` (list), `public` (bool)                                | The service requires `PUBLISH_SECRET` and `PUBLISH_ALLOWED_EMAILS` (`publish/README.md`); the spec's `publish_api_key` is minted on the account page and lives on the Mac, so it is not a cluster input.                                                                                                                                                       |
| Publish probes        | `tcpSocket` on 8080                                                                                                                                                                                                                            | The service has no health route; `/account/sign-in` would couple readiness to Pocket ID. The container listens only after `auth migrate` succeeded.                                                                                                                                                                                                            |
| Backups               | career-ops: tar of `/data` (read-only mount) in the server image, fails unless `./data/applications.md` is in the tar. publish: `VACUUM INTO` through `node:sqlite` in the publish image (read-write mount), fails on an empty `shares` table. | House pattern: fail before the prune when the volume looks empty.                                                                                                                                                                                                                                                                                              |
| Section position      | `[career_ops]` after `[cliproxyapi]`, before `[github_runner]`                                                                                                                                                                                 | New sections append before the runner and the nodes.                                                                                                                                                                                                                                                                                                           |

## Review Focus

1. `[career_ops]` set with `[pocket_id]` absent: refused with a message naming `career_ops`. (Task 1 fixture.)
2. `[career_ops]` set with `[volume_backup]` absent: refused. (Task 1 fixture.)
3. `public = true` without `pocket_id.public`: refused. (Task 1 test.)
4. A fixture without `[career_ops]` renders nothing under `kubernetes/apps/career-ops/` (every template gated on `career_ops_enabled`). (Task 5.)
5. `${SECRET_DOMAIN}` and `$`-bearing secrets: no `${` inside the CronJob scripts, because Flux `envsubst --strict` runs on them. (Task 2 and 3 review.)

---

### Task 1: Validator, sample, schema, fixtures

**Files:**

- Modify: `template/scripts/validate.py` (a `CareerOps` model after `CliProxyApi`; `career_ops: CareerOps = CareerOps()` on `Config` after `cliproxyapi`; a `career_ops_enabled` computed field; cross-field checks at the end of the `Config` validator)
- Modify: `template/scripts/test_validate.py`
- Modify: `cluster.sample.toml` (a `[career_ops]` block between `[cliproxyapi]` and `[github_runner]`, banner and comment style as its neighbours)
- Regenerate: `cluster.schema.json` with `just template schema`
- Modify: `.github/template-tests/valid/public.toml` (a `[career_ops]` block after `[cliproxyapi]`, `public = true`)
- Create: `.github/template-tests/invalid/career-ops-without-pocket-id.toml`, `.github/template-tests/invalid/career-ops-without-volume-backup.toml` (copy `itsaplan-without-rustfs.toml`'s shape; each with `[postgres.backup]` plus what the check needs and a `# expect:` line)
- Modify: `.github/workflows/template-e2e.yaml` (both fixture names in the `validate-invalid` matrix)
- Modify: `.claude/rules/templates.md` (add `career_ops_enabled` to the computed-field list)

**Interfaces:**

- Produces: `career_ops_enabled: bool` (true when `career_ops.oidc_client_secret != ""`), and `career_ops.<field>` for the templates.

```python
class CareerOps(Model):
    # The Pocket ID client the gateway signs dashboard users in with (callback https://career.<domain>/oauth2/callback).
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    oidc_client_secret: Secret = ""
    # From `claude setup-token` on the Mac; lasts one year.
    claude_oauth_token: Secret = ""
    # Signs share-page cookies and feedback links; rotating it logs every visitor out.
    publish_secret: LongSecret = ""
    # Better Auth's secret for the publish account page; rotating it signs everyone out.
    publish_auth_secret: LongSecret = ""
    # The second Pocket ID client, for the publish account page (callback https://cv.<domain>/api/auth/callback/pocket-id).
    publish_oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    publish_oidc_client_secret: Secret = ""
    # Who may sign in to the publish account page and mint API keys.
    publish_allowed_emails: list[EmailAddress] = []
    # Also attach the dashboard route to the external gateway.
    public: bool = False

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "career_ops", (seven string fields above))
        if self.oidc_client_secret and not self.publish_allowed_emails:
            raise ValueError("career_ops.publish_allowed_emails is required: nobody could sign in to the publish account page")
        if self.publish_allowed_emails and not self.oidc_client_secret:
            raise ValueError("career_ops.publish_allowed_emails requires oidc_client_secret: career-ops only runs when the client is set")
        return self
```

Cross-field checks on `Config` (messages are the `# expect:` lines):

- `career_ops requires pocket_id: Pocket ID is the dashboard's only login`
- `career_ops requires ingress.mode other than 'none': the share pages are served on the external gateway`
- `career_ops requires volume_backup: the data volume is the only copy of the tracker`
- `career_ops.public requires oidc_client_secret: career-ops only runs when the client is set`
- `career_ops.public requires pocket_id.public: a visitor from the internet must reach the Pocket ID login`

- [ ] **Step 1: Write the failing tests** in `test_validate.py` after the `CLIPROXYAPI` tests: a `CAREER_OPS = POCKET_ID | VOLUME_BACKUP-like overrides` dict (reuse an existing volume-backup dict if one exists, else `{"volume_backup.bucket": "fake-volumes", "volume_backup.access_key": "fakev", "volume_backup.secret_key": "fakev"}` on `private.toml`), then `test_career_ops_enabled_only_when_configured`, `test_partial_career_ops_names_missing_field`, `test_career_ops_requires_allowed_emails`, `test_career_ops_requires_pocket_id`, `test_career_ops_requires_volume_backup`, `test_career_ops_requires_ingress`, `test_career_ops_public_requires_public_pocket_id`, each `pytest.raises(ConfigError, match=...)` on the message above.
- [ ] **Step 2: Run** `uv run --locked pytest template/scripts/test_validate.py -q -k career_ops` and see them fail (unknown key `career_ops`).
- [ ] **Step 3: Implement the model, the computed field and the checks.** Then the sample block, the fixtures, the e2e matrix, `just template schema`, `.claude/rules/templates.md`.
- [ ] **Step 4: Run** `uv run --locked pytest template/scripts/test_validate.py -q` → all pass, including `test_invalid_fixture_rejected` for both new fixtures and the layout test for `public.toml`.
- [ ] **Step 5: Commit** `feat(career-ops): validate the [career_ops] section`.

### Task 2: career-ops namespace and the web app

**Files:**

- Create: `template/config/kubernetes/apps/career-ops/kustomization.yaml.j2`, `namespace.yaml.j2` (restricted; copy `reactive-resume/`)
- Create: `template/config/kubernetes/apps/career-ops/career-ops/ks.yaml.j2` (no `dependsOn`; `wait: false`)
- Create under `template/config/kubernetes/apps/career-ops/career-ops/app/`: `kustomization.yaml.j2`, `ocirepository.yaml.j2` (app-template 5.3.0, copy), `helmrelease.yaml.j2`, `httproute.yaml.j2`, `securitypolicy.yaml.j2`, `oidc-secret.sops.yaml.j2`, `secret.sops.yaml.j2`, `networkpolicy.yaml.j2`, `scan-cronjob.yaml.j2`, `backup-cronjob.yaml.j2`, `backup-secret.sops.yaml.j2` (the last two gated on `career_ops_enabled and volume_backup_enabled` and listed under that condition in the kustomization, as `pegaprox` does)

Every file is wrapped in `#% if career_ops_enabled %#` ... `#% endif %#`.

**HelmRelease `career-ops`** (values):

- `controllers.web`: `strategy: Recreate`, `annotations: reloader.stakater.com/auto: "true"`, container `app` with the server image, env `CAREER_OPS_ROOT: /data`, `CAREER_OPS_WEB_ALLOWED_HOSTS: career.${SECRET_DOMAIN}`, `CAREER_OPS_SCHEDULER: external`, `CAREER_OPS_SCHEDULER_DESCRIPTION: "CronJob career-ops-scan-tick, every 15 minutes"`, `envFrom: secretRef career-ops-secret`; probes: liveness, readiness and startup all `httpGet` `/api/healthz` port 3000 with `httpHeaders: [{name: Host, value: localhost}]` (startup `failureThreshold: 60`, period 5); `securityContext` `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`; resources requests `cpu: 250m`, `memory: 1Gi`, limits `memory: 3Gi`.
- `defaultPodOptions.securityContext`: `runAsNonRoot`, `runAsUser/runAsGroup/fsGroup: 1000`, `seccompProfile RuntimeDefault`.
- `service.app`: `forceRename: career-ops-web`, port `http: 3000`.
- `persistence`: `data` (pvc, `local-path`, RWO, 10Gi, `forceRename: career-ops-data`, `retain: true`, mount `/data`), `home` (pvc, `local-path`, RWO, 1Gi, `forceRename: career-ops-home`, `retain: true`, mount `/home/app`), `tmp` emptyDir at `/tmp`, `cache` emptyDir at `/home/app/.cache` (a mount inside `home`; list it after `home`), `shm` emptyDir `medium: Memory`, `sizeLimit: 1Gi` at `/dev/shm`.
- Comment the one non-obvious why in each place: one replica because `lib/dir-lock.mjs` judges lock staleness by pid; `Host: localhost` because loopback hosts are always admitted by the guard.

**HTTPRoute `career-ops`**: hostnames `["career.${SECRET_DOMAIN}"]`, parentRefs `envoy-internal` and, `#% if career_ops.public %#`, `envoy-external`; one rule `backendRefs: career-ops-web:3000`, `timeouts: {request: 900s}` (the `/api/run` SSE stream lasts up to 800 s).

**SecurityPolicy `career-ops`**: copy `media/shared/app/securitypolicy.yaml.j2`, `targetRefs: [{group: gateway.networking.k8s.io, kind: HTTPRoute, name: career-ops}]` instead of `targetSelectors`, `clientID: career_ops.oidc_client_id`, `clientSecret.name: career-ops-oidc`, `cookieNames.idToken: career-ops-id-token`, same JWT provider and `cluster_admins` rule.

**Secrets**: `career-ops-oidc` with `client-secret`; `career-ops-secret` with `CLAUDE_CODE_OAUTH_TOKEN`.

**NetworkPolicy `career-ops`**: podSelector `app.kubernetes.io/name: career-ops`, `app.kubernetes.io/controller: web`; ingress TCP 3000 from `namespaceSelector kubernetes.io/metadata.name: network` and from `podSelector matchLabels career-ops.io/role: scan-tick` (same namespace). Comment: the gateway is the access control; the guard admits any client sending `Host: localhost`.

**CronJob `career-ops-scan-tick`**: `*/15 * * * *`, `concurrencyPolicy: Forbid`, history limits 1/1, `backoffLimit: 0`, `activeDeadlineSeconds: 60`, pod template label `career-ops.io/role: scan-tick`, `restartPolicy: Never`, `automountServiceAccountToken: false`, restricted securityContext (`runAsNonRoot`, uid 65534, seccomp, drop ALL, read-only root), image `docker.io/curlimages/curl:8.17.0@sha256:...` (read the digest with `crane digest`), command `curl -fsS -X POST -H 'Host: localhost' http://career-ops-web.career-ops.svc:3000/api/scheduler`, requests 10m/16Mi, limit 64Mi.

**CronJob `volume-backup`** (`backup-cronjob.yaml.j2`) and Secret `volume-backup` (`backup-secret.sops.yaml.j2`): copy `pegaprox`'s pair. Schedule `"50 1 * * *"`. Pod uid/gid/fsGroup 1000. Init container `snapshot` in the server image: `tar -czf /work/out.tar.gz -C /data . || rc=$?; [ "$rc" -le 1 ]`, then `tar -tzf /work/out.tar.gz | grep -qxF ./data/applications.md` (fails on an empty volume, before the prune). Mount claim `career-ops-data` at `/data` **readOnly: true**. Upload container unchanged except the key prefix `volumes/career-ops/career-ops-<timestamp>.tar.gz`. No `${` in the scripts.

- [ ] **Step 1: Write the files.**
- [ ] **Step 2: Render check**: run Task 5's render script on `public.toml` and read `kubernetes/apps/career-ops/` in the scratch copy.
- [ ] **Step 3: Commit** `feat(career-ops): deploy the dashboard behind Pocket ID`.

### Task 3: publish app

**Files:** under `template/config/kubernetes/apps/career-ops/publish/`: `ks.yaml.j2`; `app/kustomization.yaml.j2`, `ocirepository.yaml.j2`, `helmrelease.yaml.j2`, `httproute.yaml.j2`, `secret.sops.yaml.j2`, `networkpolicy.yaml.j2`, `backup-cronjob.yaml.j2`, `backup-secret.sops.yaml.j2`. Add `./publish/ks.yaml` to `career-ops/kustomization.yaml.j2`.

**HelmRelease `publish`**: controller `publish`, `Recreate`, reloader annotation; container `app` with the publish image; env `PUBLISH_BASE_URL: https://cv.${SECRET_DOMAIN}`, `PUBLISH_BIND: 0.0.0.0`, `PUBLISH_PORT: "8080"`, `PUBLISH_DB: /data/publish.db`, `PUBLISH_TRUSTED_PROXIES: "#{ kubernetes.pod_cidr }#"`, `PUBLISH_CLIENT_IP_HEADER: x-forwarded-for`, `POCKET_ID_CLIENT_ID: "#{ career_ops.publish_oidc_client_id }#"`, `POCKET_ID_DISCOVERY_URL: https://auth.${SECRET_DOMAIN}/.well-known/openid-configuration`, `PUBLISH_ALLOWED_EMAILS: "#{ career_ops.publish_allowed_emails | join(',') }#"`; `envFrom` `publish-secret`; probes liveness and readiness `tcpSocket` 8080 (custom spec), startup the same with `failureThreshold: 30`; restricted securityContext; resources 50m/128Mi, limit 512Mi; `defaultPodOptions.securityContext` uid/gid/fsGroup 1000; `service.app` port 8080; persistence `data` (pvc `local-path` RWO 1Gi, `forceRename: publish-data`, `retain: true`, mount `/data`), `tmp` emptyDir `/tmp`. Comment on the trusted-proxies line: the service matches peers exactly today, so the CIDR takes effect once career-ops matches CIDRs.

**HTTPRoute `publish`**: `cv.${SECRET_DOMAIN}` on `envoy-external` only, backend `publish:8080`, no SecurityPolicy (share pages are public; the service has its own Better Auth).

**Secret `publish-secret`**: `PUBLISH_SECRET`, `PUBLISH_AUTH_SECRET`, `POCKET_ID_CLIENT_SECRET`.

**NetworkPolicy `publish`**: podSelector `app.kubernetes.io/name: publish`, `app.kubernetes.io/controller: publish`, ingress TCP 8080 from the `network` namespace only.

**CronJob `volume-backup`** in this folder (names are namespaced per app folder, so call it `publish-volume-backup`, and the Secret `publish-volume-backup`): schedule `"0 2 * * *"`, pod uid 1000, init `snapshot` in the publish image running `node -e` with `node:sqlite`: open `/data/publish.db`, `VACUUM INTO '/work/publish.db'`, open the copy, assert `pragma integrity_check` is `ok` and `select count(*) from shares` is > 0 (an app that lost its volume starts empty; fail before the prune), then `tar -czf /work/out.tar.gz -C /work publish.db` (the alpine image's tar is BusyBox; a single `-C` with one member is fine) and `tar -tzf` must list `publish.db`. Claim `publish-data` mounted read-write (WAL rule). Upload container as `pegaprox`, prefix `volumes/career-ops/publish-<timestamp>.tar.gz`.

- [ ] **Step 1: Write the files.**
- [ ] **Step 2: Render check** as in Task 2.
- [ ] **Step 3: Commit** `feat(career-ops): deploy the publish share-page service at cv`.

### Task 4: Renovate, rules, index

**Files:**

- Modify: `.renovaterc.json5`: add both images to `matchPackageNames` of the two docs-image rules (pinDigests; digest automerge with `ignoreTests`, same reason: the image's own repository built and tested it) and as `!` exclusions in the tier-1 digest rule. Update the three descriptions to say "docs and career-ops images".
- Create: `.claude/rules/apps/career-ops.md` with `paths` on `template/config/kubernetes/apps/career-ops/**` and `kubernetes/apps/career-ops/**`, one bullet per fact in the house style (what gates it, the two apps and hosts, one replica and why, the `Host: localhost` rule, the NetworkPolicy and why, the CronJobs and schedules, the token renewal procedure: `claude setup-token` yearly, paste into `cluster.toml`, `just configure`, reloader restarts the pod; operator checks: Pocket ID must send `email_verified: true` for the publish sign-in; `PUBLISH_TRUSTED_PROXIES` exact-match caveat; the `public` fixture sets the section).
- Modify: `CLAUDE.md` line 98: add `career-ops` to the index list.

- [ ] **Step 1: Write the files.** `oxfmt --check .` clean. Keep `CLAUDE.md` under 20,000 characters (`wc -c`).
- [ ] **Step 2: Commit** `chore(career-ops): pin the images in Renovate and record the app's rules`.

### Task 5: Render proof

- [ ] **Step 1:** write `.claude/plans/2026-11-07-career-ops-deploy/render-check.sh` (bash, `set -euo pipefail`): make a scratch copy of the tracked files (as `.claude/hooks/stop.py` `make_scratch` does, `git ls-files --cached --others --exclude-standard`), seed `age.key` (`age-keygen`), `deploy.key` (`ssh-keygen`), `flux-webhook-token.txt`, `cloudflare-tunnel.json` as `seed_secrets` does, copy the fixture given as `$1` to `cluster.toml` in the scratch copy, run `uv run --quiet --locked --no-dev makejinja` there with `SOPS_AGE_KEY_FILE` and `SOPS_CONFIG` pointing into the scratch copy and `UV_PROJECT_ENVIRONMENT` at the repo's `.venv`, then `oxfmt --check ./.sops.yaml ./bootstrap ./kubernetes ./talos`, then `bash template/resources/kubeconform.sh kubernetes`, and print the scratch path. It never touches the worktree's rendered trees.
- [ ] **Step 2:** run it on `public.toml`: render, oxfmt and kubeconform pass; `kubernetes/apps/career-ops/` holds every file above. Run it on `private.toml`: `kubernetes/apps/career-ops/` is absent or empty.
- [ ] **Step 3:** `uv run --locked pytest template/scripts/test_validate.py -q` passes; `oxfmt --check .` on the worktree passes.
- [ ] **Step 4:** record the results in `VERIFY.md`; commit `docs(career-ops): record the unit verification`.
