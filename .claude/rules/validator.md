---
paths:
    - "template/scripts/**"
    - "cluster.sample.toml"
    - "cluster.schema.json"
    - ".github/template-tests/**"
---

# Changing the cluster.toml schema

`template/scripts/validate.py` is the only definition of `cluster.toml`. A schema change touches four places in one change:

1. Update the pydantic model in `validate.py`. Every model subclasses `Model` (`extra="forbid"`), so an unknown key is an error. Put cross-field checks in a `@model_validator(mode="after")` that raises `ValueError` with a message naming the field path, as in `nodes[0].address`.
2. Document the field in `cluster.sample.toml`, with the same comment style as the fields around it: what the field is, then REQUIRED or the default, then an example.
3. Run `just template schema` to regenerate `cluster.schema.json`. Don't edit that file by hand, because the tests fail when it drifts from the model.
4. Add fixtures. A config that must be accepted goes in `.github/template-tests/valid/`. A config that must be rejected goes in `.github/template-tests/invalid/`. Add the fixture name to the `matrix.fixture` list of the matching job in `.github/workflows/template-e2e.yaml` (`validate-valid` or `validate-invalid`).

Then run `uv run --locked pytest template/scripts/test_validate.py -q`. The Stop hook also runs it when `template/scripts/` changed, and it renders every valid fixture.

## Keeping cluster.toml and cluster.sample.toml in step

`cluster.sample.toml` is the layout of record: the order of the sections, the banner comment above each app section, and the comment style of each field. `cluster.toml` and every fixture mirror it. A config may leave an optional section out, but never reorders what it has. `just template check-layout` compares the section order of `cluster.toml` with the sample and runs first in `just configure`, and pytest checks every valid fixture the same way.

When a new section lands, add it to `cluster.toml` as well, in the sample's position, with the values left for the user to fill:

- Copy the sample's whole block: the banner, the `[section]` header and the commented-out keys.
- Insert it after the end of the section that precedes it in the sample. Find that section's header, then the next header or banner after it, and insert there. Never anchor on the next header alone: a banner comment sits above each header, so the block would land inside it. That is how `[pegaprox]` ended up in the Talos block on 2026-10-05.
- Do it with a script that prints only line numbers, never the file's lines.
- Run `just template check-layout`, then `taplo check --schema "file://$PWD/cluster.schema.json" ./cluster.toml`.

Templates read the validated config, so a renamed or removed field also breaks every template that uses it. Search for it with `grep -rn '<field>' template/config`.
