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

Not measured: the career-ops tar step and the publish container's start under a read-only root (no Docker daemon here, so neither image ran). The curl image digest was read with `crane digest` outside the sandbox (2026-11-08).

## Live and perf lanes (pending the operator's secrets)

The ten live lanes and the perf lane of the contract need the `[career_ops]` section in the cluster config. They run after the operator supplies:

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
