# Researching an update

The goal is a verdict backed by evidence: `safe`, `needs template change`, or `blocked`. Label each claim as
measured (a command showed it) or stated (upstream's notes say it). An update with no evidence is not `safe`; it
is unresearched.

## 1. Read the release notes for every version crossed

A jump from 1.4 to 1.7 crosses 1.5, 1.6 and 1.7. Read all three, not only the last.

- Find the upstream repository for the app in `apps.md`.
- List releases with `gh release list -R <owner>/<repo> --limit 30`, then read each with
  `gh release view <tag> -R <owner>/<repo>`.
- Many repositories tag the chart and the application separately. The chart tag is the one pinned here.
- Look for the words upgrade, breaking, migration, deprecated, removed, renamed, requires, and minimum.
- When the project publishes an upgrade guide, read the section for the target version. `apps.md` lists the ones
  known to exist.

A `major` bump always has a reason. Find it before doing anything else.

## 2. Compare the two chart versions

```sh
.claude/skills/update-apps/scripts/compare-chart.sh <namespace> <app> <old-version> <new-version>
```

It renders both versions with the values from the rendered `HelmRelease`, and writes three diffs to a temporary
directory. On a non-zero exit, read stderr before concluding anything. A network or sandbox error and a missing
app directory are problems with the run. A template error from the new version with the current values is a
finding.

An image-only pin, such as `cloudflared`, has no chart to compare. Skip this step for it. Rely on the release
notes, and check that every argument and environment variable this repo passes to the container still exists.

Read each diff for these:

| Diff             | Finding                                                     | Verdict                                              |
| ---------------- | ----------------------------------------------------------- | ---------------------------------------------------- |
| `defaults.diff`  | A key this repo sets was renamed or removed                 | needs template change                                |
| `defaults.diff`  | A new key with no default that the chart requires           | needs template change                                |
| `defaults.diff`  | A default changed for a key this repo leaves unset          | read the notes, then decide                          |
| `rendered.diff`  | A selector, `volumeClaimTemplates` or `serviceName` changed | blocked until a migration is planned                 |
| `rendered.diff`  | An `apiVersion` changed                                     | check the cluster serves it: `kubectl api-resources` |
| `rendered.diff`  | A container image moved registry or changed name            | check `apps.md` for an image override                |
| `resources.diff` | A resource was removed or renamed                           | check nothing else in `kubernetes/` refers to it     |
| `resources.diff` | A CustomResourceDefinition was added, removed or changed    | see the CRD section below                            |

The values the comparison uses still contain Flux placeholders such as `${SECRET_DOMAIN}`. That is fine for a
diff. It means a rendered hostname is not the real one.

## 3. Check this repo's values against the new chart

List the keys this repo sets and confirm each still exists in the new defaults:

```sh
yq '.spec.values | .. | select(tag != "!!map" and tag != "!!seq") | path | join(".")' \
    kubernetes/apps/<namespace>/<app>/app/helmrelease.yaml
```

A key missing from the new defaults is not proof of a problem, because charts accept free-form maps such as
`affinity` and `podAnnotations`. It is a reason to search the chart's templates for that key.

## 4. Check CustomResourceDefinitions

Flux applies CRD changes on upgrade, because every `HelmRelease` inherits `upgrade.crds: CreateReplace` from
`template/config/kubernetes/flux/cluster/ks.yaml.j2`. That makes a CRD change take effect, and it also makes a
removed field or version take effect.

- A CRD that drops a version the cluster still stores objects in cannot be applied. Check what is stored:
  `kubectl get crd <name> -o jsonpath='{.status.storedVersions}'`. A stored version missing from the new CRD is
  `blocked` until the objects are migrated.
- A CRD this repo uses directly, such as `DNSEndpoint`, `Gateway` or `HTTPRoute`, needs the manifests under
  `template/config/kubernetes/` checked against the new schema. `just configure` runs kubeconform on them.

## 5. Check compatibility with the platform

- Kubernetes: `kubectl version -o json | jq -r '.serverVersion.gitVersion'`. Compare with the chart's
  `kubeVersion` in `helm show chart <url> --version <new>` and with the release notes.
- Talos specifics for Cilium, CoreDNS and Spegel are in `apps.md`.

## 6. Decide

- `safe`: the notes name nothing that applies here, and the diffs show no finding from the table.
- `needs template change`: a finding has a known fix in the `.j2` source. Name the file and the change.
- `blocked`: a finding needs a migration, a manual step on the cluster, or a decision from the user. Say what is
  needed and stop.

When something could not be checked, say so in the report. Do not round it up to `safe`.
