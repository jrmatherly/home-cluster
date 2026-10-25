---
name: update-apps
description: Updates the chart and image versions pinned in this repo's templates, checks each update for breaking changes, makes the template changes the new version needs, re-renders, and verifies the deployment. Use when the user wants to "update our apps", "bump cilium", "update cert-manager to the latest chart", "check for app updates", "is there a new chart version", "what breaks if we update X", or invokes /update-apps. Not for Talos or Kubernetes version upgrades, and not for adding a new app.
argument-hint: "[app ...] | all | --check | --auto"
---

# Update Apps

Move one or more templated apps to a newer chart or image version without breaking the cluster. The end state is a
pushed commit per app, a healthy Flux release at the new version, and a short report of what changed and why it was
safe.

## Scope

- **In scope:** chart tags in `template/config/kubernetes/apps/**/app/ocirepository.yaml.j2`, image tags in
  `helmrelease.yaml.j2` values, and explicit chart versions in `template/config/bootstrap/helmfile/*.yaml.j2`.
- **Out of scope:** the Talos and Kubernetes versions in `template/config/talos/topf.yaml.j2`. Those are node
  upgrades (`just talos upgrade-node`, `just talos upgrade-k8s`), not app updates. Say so and stop.
- **Not this skill, reviewed by hand from their Renovate PRs:** mise tools (`.mise/`), GitHub Actions, the
  docs site's npm dependencies (`docs/package.json`, including `@cloudflare/nimbus-docs`, which has its own
  migrate step in CLAUDE.md), the `home-operations/renovate-presets` pin in `.renovaterc.json5`, and the
  docs Dockerfile's base images. Name them in the report when they are open, so they are not forgotten,
  and leave them.

## Arguments

- `<app> ...` updates the named apps.
- `all` updates every app with a pending version.
- `--check` runs steps 1 to 4 and stops. It edits nothing and renders nothing.
- `--auto` is research only, over the open Renovate pull requests instead of the inventory. It runs steps 1
  to 4, writes a verdict per PR to `verdicts.json` and the report to the summary destination in step 4, and
  merges nothing and comments nothing. The merge belongs to `scripts/auto-merge.sh`, because the research
  reads release notes and PR bodies that anyone upstream can write, so its verdicts are data the script
  re-checks before it touches `main`.
- With no argument, run the inventory, show the table, and ask which apps to update.

## Workflow

Steps 1 to 4 cover every target at once and end in one report. Steps 5 to 8 then run once per approved app, in
order, and the next app starts only when the current one is healthy.

1. **Inventory.** Run `uv run --script .claude/skills/update-apps/scripts/inventory.py [app ...]`. It prints every
   pin with its newest stable tag and the size of the bump. A non-zero exit means a lookup failed or found no
   stable tag; read stderr and resolve it before trusting the table. Run `gh pr list` as well. When Renovate
   already has a pull request for a target, name it in the report so the user can close it once the update lands.
   With `--auto`, run `git pull --ff-only` first, then
   `gh pr list --json number,title,headRefOid,files` instead of the inventory, and take the app, the two
   versions and the bump from each PR's title and files. A PR whose files are outside the scope above is `not
   ours`.
2. **Plan the order.** Read `references/apps.md` for apps that must move together and for the order to take when
   several are pending.
3. **Research each target.** Read `references/breaking-changes.md` and follow it. With three or more targets, give
   each app's research to its own subagent and keep only the verdicts. End with one verdict per app: `safe`,
   `needs template change`, or `blocked`. With `--auto`, write them to `verdicts.json`, an array of
   `{pr, app, namespace, kind, from, to, bump, headRefOid, verdict, evidence}`: `app` is the key in
   `references/auto-checks.yaml` or `references/apps.md`, `kind` is `chart` or `image`, `headRefOid` is the
   PR head the research read, `verdict` adds `not ours` to the three above, and `evidence` is one sentence
   with its label (measured or stated). In the action, `--json-schema` makes that array the structured output.
4. **Report and get approval.** Read `templates/report.md` and report in that shape, then stop and wait. A push to
   `main` deploys, because Flux reconciles from Git. A `blocked` app goes no further, and a `--check` run ends
   here. An `--auto` run ends here too, with the report in the auto-run shape of `templates/report.md`
   written to `$GITHUB_STEP_SUMMARY` when that is set, else to
   `private/findings/<date>-auto-updates/README.md`.
5. **Edit the templates.** Change the tag in the `.j2` source, plus any value the new version renamed, removed, or
   now requires. Never edit the rendered copy under `kubernetes/` or `bootstrap/`. A change that needs a new
   `cluster.toml` field follows `.claude/rules/validator.md`. When the update needed a step that
   `references/apps.md` does not mention, add it there now so it lands in the same commit. That file is only as
   current as this step keeps it.
6. **Render and validate.** Run `just configure`. Restore the re-encrypted secret files as `CLAUDE.md` describes.
   Confirm `git status` lists only this app's template and rendered files. Run `just template test-helmfile` when
   the app is also a bootstrap release, meaning it is listed in `template/config/bootstrap/helmfile/apps.yaml.j2`.
   When the render fails or the diff holds something the report did not predict, stop and report it instead of
   committing.
7. **Commit, push, wait, verify.** Commit as `chore(<namespace>): update <app> to <version>` and push. Run
   `just kube reconcile`, then wait for the release and run the checks, both as `references/apps.md` describes.
   Flux upgrades asynchronously, so a check made before the wait sees the old version still healthy.
8. **Roll back on failure.** Flux retries a failed Helm upgrade twice and then rolls the release back itself. Make
   Git match: `git revert` the commit and push. Report the failure with the controller's message from
   `flux get hr -n <namespace> <app>`, and do not start the next app.

## Runs in CI

The weekly workflow (`.github/workflows/update-apps.yaml`) has two jobs. `research` runs this skill with
`--auto` through the Claude Code action on a GitHub-hosted runner with a read-only token, so it can read PRs
and release notes and write nothing. `apply` runs `scripts/auto-merge.sh verdicts.json` on the self-hosted
runner in the cluster with no model: it merges a `safe` verdict only when the PR was opened by the Renovate
app from a same-repository `renovate/` branch (the repo is public, so a verdict alone is never enough), the
PR head is the one researched, the diff changes version strings alone and only under the app's own directory,
the app is in `references/auto-checks.yaml` and not marked `Tier 1: never` in `references/apps.md`, and Flate
passes when the head is behind `main`; then it waits for Flux to
apply the merge commit and runs the app's checks. A failed check reverts that merge and stops, a check that
cannot run stops with no revert, and every other verdict gets one comment opening with
`<!-- update-apps verdict -->`. `cluster.toml` is absent there, so the domain comes from `CLUSTER_DOMAIN`.
`scripts/bootstrap-drift.sh` never runs on the runner, because it reads the Helm release Secrets, which the
runner's RBAC refuses; that is why the six bootstrap charts are not in `auto-checks.yaml`.
`scripts/test-auto-merge.sh` is the script's test, with fake `gh`, `kubectl`, `flux`, `git` and `flate` on
`PATH`; run it after any change to the script or the registry.

## Gotchas

- **The inventory reads templates, not the cluster.** A version in the table is what Git pins. Compare with
  `flux get hr -A` when the two might differ.
- **Both scripts and `helm`, `flux`, `kubectl` and `gh` need network or cluster access.** Inside the Bash sandbox
  they fail with an x509, "connection closed" or "operation not permitted" error. That is the sandbox, not the
  tool. Rerun the same command outside the sandbox through the normal permission prompt.
- **Run `just configure` on a line of its own.** The sandbox exclusion matches the bare command. With a pipe or a
  second command it runs sandboxed and fails on the `uv` cache with "operation not permitted".
- **Never print the validator's full output.** `template/scripts/validate.py cluster.toml` writes the whole
  config, including `dns.token`, to stdout. Pipe it through `jq` and select the fields needed.
- **A chart that renders is not a chart that upgrades.** Immutable fields, such as a Deployment's selector
  labels, render cleanly and then fail on the live release. The comparison script shows them; read the diff.
- **A release that has never succeeded cannot roll back.** When an install fails and the fix arrives as an
  upgrade that also fails, the HelmRelease goes `Stalled` with `MissingRollbackTarget` and stops retrying. Once
  the workload itself is healthy, `flux reconcile hr <app> -n <namespace> --force` runs one upgrade and clears it.
- **One chart is outside Flux.** `prometheus-operator-crds` is installed only at bootstrap. See
  `references/apps.md` before touching its version.
- **Pre-releases are ignored on purpose.** The inventory only offers tags shaped like `1.2.3`, `v1.2.3`, `1.2` or
  `1.2.3.4` (missing parts read as 0, so a `1.38` pin shows `1.38.0` as latest with bump `none`). A two-part
  latest may be a floating tag; pin the full tag when one exists. A tag can still be a release upstream marks
  pre-release, as the Servarr builds are (`references/apps.md`). A pin
  with a variant suffix, such as `2.9.1-alpine` or `v4.11.0-gpu-nvidia-cuda-12-llama-cpp`, is only compared with
  tags of that same variant.
- **A `helmrepo` row is a classic HelmRepository chart** (`csi-driver-nfs`, `rustfs`), read from the
  repository's `index.yaml`. `scripts/compare-chart.sh` fails on it because it reads `ocirepository.yaml`:
  fetch both chart tarballs from the index and `helm template` them with the rendered HelmRelease values.
- **Bump `digest` means the tag did not move but its digest did.** Renovate opens a PR for it (a rebuilt
  base image, usually). The tier 1 rules in `.renovaterc.json5` merge it on their own on the weekend once
  Flate passes, unless it is a LocalAI, rustfs rc, pegaprox or Servarr image (stated, the digest rule). They
  merge patch PRs the same way for the apps in the "Tier 1 automerge, patch" allowlist, and the docs digest
  merges at once as a branch. A PR still open on Monday is one Flate failed, one no tier 1 rule covers, or
  one under three days old. A digest-only PR needs no research beyond reading what the rebuild changed; merge
  it by hand with `gh pr merge --rebase`.
- **A hand merge passes the researched head, never a fresh one.** Renovate rebases a PR whenever a newer
  build appears, so `gh pr merge --rebase --match-head-commit <headRefOid from the verdict>` refuses a PR
  that moved since the research. Refetching the head first defeats the gate: the SearXNG PR picked up an
  unresearched same-day build four minutes before its merge on 2026-10-25 (measured). The full 40-character
  SHA is required; GitHub rejects a short one.
- **A date tag with a commit suffix compares by date.** `2026.10.23-68647d080` reads as a build of that day,
  so SearXNG's row shows a newer day. Same-day builds tie, and the table cannot tell which one `latest`
  carried; `references/apps.md` says how to pick.
- **Images it skips.** The docs image (`:latest`, Renovate moves its digest) and the model images under
  `ghcr.io/jrmatherly/models/` (hand-bumped, see `references/apps.md`).
- **quay.io answers the tag list with 503 at times** (both LocalAI backend runs on 2026-10-24). The row reads
  `?` with a stderr line; check the one tag by hand with a HEAD on `/v2/<name>/manifests/<tag>`.

## Resources

- `scripts/inventory.py` — lists every pinned chart and image with its newest stable tag. Run it, do not read it.
- `scripts/compare-chart.sh` — renders two chart versions with this cluster's values and diffs them. Run it, do
  not read it.
- `scripts/upstream-diff.sh` — diffs two tags of an upstream GitHub repository through a shallow clone that
  can run nothing (no external diff, pager or user config). Run it, do not read it.
- `scripts/bootstrap-drift.sh` — lists live fields the bootstrap's `helm` field manager still owns that the
  current release manifest dropped, for the six charts `just bootstrap apps` installed; `--apply` releases
  them. Run it after any of those charts drops a key (step 7), because helm-controller cannot prune them.
  It exits 1 when a release is not readable, which is what happens on the runner.
- `scripts/auto-merge.sh` — the apply step of the weekly run, described under "Runs in CI". Run it, do not
  read it; `--dry-run` prints the action per PR and touches nothing.
- `scripts/test-auto-merge.sh` — its behaviour test.
- `references/auto-checks.yaml` — the apps the script may merge, each with the Flux object to wait on and the
  checks to run. An app not in it is only ever merged by hand.
- `references/breaking-changes.md` — how to research an update and what counts as a finding. Read in step 3.
- `references/apps.md` — per-app upstream sources, coupling, update order, the post-push wait, and the health
  checks. Read in steps 2 and 7.
- `templates/report.md` — the shape of the approval report. Read before reporting in step 4.
