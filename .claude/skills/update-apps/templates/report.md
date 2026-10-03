# Report shape

A suggested shape for the report in step 4, which comes before anything is edited or rendered. Keep what helps
the user decide, and drop a section that has nothing to say. Lead with the decision being asked for.

```markdown
## Updates ready for approval

| App   | From  | To    | Bump                  | Verdict                                |
| ----- | ----- | ----- | --------------------- | -------------------------------------- |
| <app> | <old> | <new> | patch / minor / major | safe / needs template change / blocked |

## <app> <old> to <new>

- **What changes for the cluster.** One or two sentences in plain language.
- **Breaking changes found.** Each one with its source: a release-note link, or the diff file and line. Write
  "none found" only after reading the notes for every version crossed.
- **Template changes planned.** File and what will change, beyond the version itself. "Version only" when that
  is all.
- **Checks run.** The comparison script's summary line and any other research check, with results.
- **Not checked.** Anything the research could not confirm, and what would confirm it.

## What approval does

Each approved app is edited, rendered, committed and pushed to `main` in turn, and a push deploys. Name the
order, say which app is the riskiest and why, and name any open Renovate pull request the update replaces.

## Rollback

Flux rolls back a failed Helm upgrade by itself. `git revert <commit>` and a push make Git match.
```
