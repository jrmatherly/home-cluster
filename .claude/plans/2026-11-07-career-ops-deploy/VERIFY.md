# PR-19 verification

## Unit

Measured 2026-11-07 in the worktree, from the repository root.

| Check                                                                                                      | Result                                                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `uv run --locked pytest template/scripts/test_validate.py -q`                                              | 310 passed, the seven `career_ops` tests and both new invalid fixtures included                                                                                                            |
| `bash .claude/plans/2026-11-07-career-ops-deploy/render-check.sh .github/template-tests/valid/public.toml` | render and `oxfmt --check` on the rendered trees pass; 14 files under `kubernetes/apps/career-ops/`                                                                                        |
| `template/resources/kubeconform.sh` on that render                                                         | exit 0; every career-ops and publish object valid or skipped by kind. Inside the sandbox kubeconform cannot verify the proxy's TLS certificate, so this ran with the sandbox off           |
| `helm template` of both HelmReleases' values on app-template 5.3.0                                         | Service `career-ops-web`, Service `publish`, claims `career-ops-data`, `career-ops-home`, `publish-data`, each with `helm.sh/resource-policy: keep`; pod labels match both NetworkPolicies |
| The render script on `.github/template-tests/valid/private.toml`                                           | render and `oxfmt` pass; `kubernetes/apps/career-ops/` does not exist                                                                                                                      |
| The publish snapshot logic under Node 24.22.2 (the image's version) on a scratch WAL database              | passes with one share, refuses an empty `shares` table with `no shares`                                                                                                                    |
| `oxfmt --check .`                                                                                          | clean                                                                                                                                                                                      |

`just configure` against the real cluster config (2026-11-08, after the operator filled `[career_ops]`): render, sops encryption, kubeconform and topf all passed; the only working-tree change was the new `kubernetes/apps/career-ops/` tree (23 files, every `*.sops.yaml` encrypted), and the 44 re-encrypted unchanged sops files were restored before the commit.

Not measured: the career-ops tar step and the publish container's start under a read-only root (no Docker daemon here, so neither image ran). The curl image digest was read with `crane digest` outside the sandbox (2026-11-08).

## Live lanes, first pass (2026-11-08 01:25 to 01:35Z, after the operator merged PR 135 as 7c93804)

| Lane                   | Result                                                                                                                                                                                                                                                                                                                            |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Deploy                 | Flux applied 7c93804; both HelmReleases Ready; pods `career-ops` (k8s-worker-1) and `publish` (k8s-gpu-1) 1/1 Running; the three claims Bound; the three CronJobs present. Both HTTPRoutes Accepted and ResolvedRefs; the SecurityPolicy "accepted".                                                                              |
| 2 (redirect half)      | `GET https://career.<domain>/` through the gateway returns 302 to `https://auth.<domain>/authorize` with `redirect_uri=https://career.<domain>/oauth2/callback` and scopes `openid profile email groups`. The sign-in itself still needs a browser.                                                                               |
| 4                      | The 01:30Z tick Job completed; the web pod answered `{"accepted":true}`; `/api/scheduler` shows `source: external` and `lastRun` 01:30:02Z; `/data/data/scheduled-jobs.json` and its `.tick` marker appeared. `pipeline.md` cannot gain rows until the data root is migrated.                                                     |
| 7 (equivalent)         | Renovate's digest automerge landed new image pins minutes after the merge (main 15c9187 and 51b193b, matching `crane digest` of both `latest` tags), so Flux rolled both Deployments under `Recreate`: the new pods came Ready, `/data` kept its files, and no `*.lock*` directory remained. The explicit pod delete was not run. |
| 10                     | `node /app/doctor.mjs --json` inside the web pod reports the data root (onboarding needed, four files missing on the empty volume), `active_cli: claude`, and the plugin list.                                                                                                                                                    |
| publish start          | The log shows `No migrations needed` and `listening on 0.0.0.0:8080, database /data/publish.db`, so the read-only root with `HOME=/tmp` works. `GET https://cv.<domain>/` is 404 and `/account` is 401, both from the service.                                                                                                    |
| 1, 3, 5, 6, 8, 9, perf | Not run: 1, 5, 6 and 8 need the migrated data root and a browser sign-in; 3 needs a pod in another namespace, which the permission classifier refuses this session; 9 fails by design until `/data/data/applications.md` exists; the perf lane needs the Mac baseline and the signed-in page.                                     |

## Migration (2026-11-08 03:17Z, extraction by the operator; checked read-only from this session at 03:20Z)

The web pod rolled at 03:01Z on a Renovate digest bump and lost the first staged tar, so the coordinator re-copied it to pod `career-ops-74b94796f4-8cfdr` and the operator extracted it by hand (this session's own extraction was refused by its permission classifier as a remote shell write). State afterwards, as reported by the coordinator and confirmed here: 128 files under `/data` at uid 1000 and mode 644, tracker at `/data/data/applications.md`, no macOS `._*` sidecars left (the coordinator deleted the 138 the Mac tar carried), no `/data/.env`, the staged tar removed, `scheduled-jobs.json` holding the one daily portals job. `node /app/doctor.mjs --json`: `onboardingNeeded false`, `unpersonalized` and `missing` empty. Coordinator-reported, not re-run here: `verify-pipeline` 0 errors and 1 pre-existing warning (report 058 JD paraphrase), `validate-portals` 0/0, node v26.13.0, `/api/scheduler` `lastRun` 03:15Z. The publish sign-in at `cv.<domain>/account` failed with "The requested OAuth 2.0 Client does not exist" because `publish_oidc_client_id` held a 32-character value, not the client's UUID (checked through the validator without printing it); the operator corrects it in the config.

## Remaining lanes (pending the data migration and a browser sign-in)

The `[career_ops]` section is filled (2026-11-08) and the apps are live. The section below is kept as the record of what the operator supplied:

| Field                                                  | Where it comes from                                                                                                                                      |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `oidc_client_id`, `oidc_client_secret`                 | A Pocket ID client with callback `https://career.<domain>/oauth2/callback`, restricted to the `cluster_admins` group                                     |
| `publish_oidc_client_id`, `publish_oidc_client_secret` | A Pocket ID client with callback `https://cv.<domain>/api/auth/callback/pocket-id`; Pocket ID must report `email_verified: true` for the allowed account |
| `claude_oauth_token`                                   | The output of `claude setup-token` on the Mac (lasts one year)                                                                                           |
| `publish_secret`                                       | `openssl rand -hex 32`                                                                                                                                   |
| `publish_auth_secret`                                  | `openssl rand -hex 32`                                                                                                                                   |
| `publish_allowed_emails`                               | The addresses allowed to sign in to `cv.<domain>/account`                                                                                                |

Then: `just configure`, restore the unchanged sops files, commit, push, watch Flux, run the lanes, save the review-gate screenshots under `private/review/`.

After the first deploy, for the dashboard's share features: sign in at `cv.<domain>/account`, mint an API key, and write `PUBLISH_URL=https://cv.<domain>` and `PUBLISH_API_KEY=cops_...` into `/data/.env` on the `career-ops-data` claim. Expect both backup CronJobs to fail (and `KubeJobFailed` to fire) until `/data/data/applications.md` and a first share exist.

## Operator checks before the first deploy

- Node floor 22.16+ on the server image: `docker run --rm ghcr.io/jrmatherly/career-ops-server:latest node --version` (not measured here: the Docker daemon was not running in this session).
