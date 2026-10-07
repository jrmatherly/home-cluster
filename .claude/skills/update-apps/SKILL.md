---
name: update-apps
description: Updates the chart and image versions pinned in this repo's templates, checks each update for breaking changes, makes the template changes the new version needs, re-renders, and verifies the deployment. Use when the user wants to "update our apps", "bump cilium", "update cert-manager to the latest chart", "check for app updates", "is there a new chart version", "what breaks if we update X", or invokes /update-apps. Not for Talos or Kubernetes version upgrades, and not for adding a new app.
argument-hint: "[app ...] | all | --check"
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

## Arguments

- `<app> ...` updates the named apps.
- `all` updates every app with a pending version.
- `--check` runs steps 1 to 4 and stops. It edits nothing and renders nothing.
- With no argument, run the inventory, show the table, and ask which apps to update.

## Workflow

Steps 1 to 4 cover every target at once and end in one report. Steps 5 to 8 then run once per approved app, in
order, and the next app starts only when the current one is healthy.

1. **Inventory.** Run `uv run --script .claude/skills/update-apps/scripts/inventory.py [app ...]`. It prints every
   pin with its newest stable tag and the size of the bump. A non-zero exit means a lookup failed or found no
   stable tag; read stderr and resolve it before trusting the table. Run `gh pr list` as well. When Renovate
   already has a pull request for a target, name it in the report so the user can close it once the update lands.
2. **Plan the order.** Read `references/apps.md` for apps that must move together and for the order to take when
   several are pending.
3. **Research each target.** Read `references/breaking-changes.md` and follow it. With three or more targets, give
   each app's research to its own subagent and keep only the verdicts. End with one verdict per app: `safe`,
   `needs template change`, or `blocked`.
4. **Report and get approval.** Read `templates/report.md` and report in that shape, then stop and wait. A push to
   `main` deploys, because Flux reconciles from Git. A `blocked` app goes no further, and a `--check` run ends
   here.
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
- **Pre-releases are ignored on purpose.** The inventory only offers tags shaped like `1.2.3` or `v1.2.3`. A pin
  with a variant prefix or suffix, such as `server-cuda-v0.5.0` or `2.9.1-alpine`, is only compared with tags of
  that same variant.
- **The inventory sees only OCI chart pins.** A chart pinned through a `helmrepository.yaml.j2` is absent from
  the table, not marked `?`. Check it by hand against the repository's `index.yaml`.

## Resources

- `scripts/inventory.py` — lists every pinned chart and image with its newest stable tag. Run it, do not read it.
- `scripts/compare-chart.sh` — renders two chart versions with this cluster's values and diffs them. Run it, do
  not read it.
- `references/breaking-changes.md` — how to research an update and what counts as a finding. Read in step 3.
- `references/apps.md` — per-app upstream sources, coupling, update order, the post-push wait, and the health
  checks. Read in steps 2 and 7.
- `templates/report.md` — the shape of the approval report. Read before reporting in step 4.
