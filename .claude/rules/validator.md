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
4. Add fixtures. A config that must be accepted goes in `.github/template-tests/valid/`. A config that must be rejected goes in `.github/template-tests/invalid/`, and its leading comment block ends with `# expect: <the first line of the error>`, which `test_invalid_fixture_rejected` matches, so the fixture proves its own check and not some unrelated error (get the line from `uv run --locked --no-dev template/scripts/validate.py <fixture>`). Add the fixture name to the `matrix.fixture` list of the matching job in `.github/workflows/template-e2e.yaml` (`validate-valid` or `validate-invalid`).

Then run `uv run --locked pytest template/scripts/test_validate.py -q`. The Stop hook also runs it whenever anything under `template/`, the sample, the schema or the fixtures changed, and it renders every valid fixture.

## Keeping cluster.toml and cluster.sample.toml in step

`cluster.sample.toml` is the layout of record: the order of the sections, the banner comment above each app section, and the comment style of each field. `cluster.toml` and every fixture mirror it. A config may leave an optional section out, but never reorders what it has. `just template check-layout` compares the section order of `cluster.toml` with the sample and runs first in `just configure`, and pytest checks every valid fixture the same way.

When a new section lands, add it to `cluster.toml` as well, in the sample's position, with the values left for the user to fill:

- Run `just template scaffold <section>` (`template/scripts/scaffold.py`, added 2026-10-25). It copies the sample's whole block, the banner, the `[section]` header and the commented-out keys, inserts it after the end of the section that precedes it in the sample, and prints line numbers only, never the file's lines. It anchors on the preceding section because a banner comment sits above each header, and anchoring on the next header put `[pegaprox]` inside the Talos block on 2026-10-05. It refuses a section the config already has.
- Then `taplo check --schema "file://$PWD/cluster.schema.json" ./cluster.toml`, outside the sandbox, where taplo's proxy lookup panics.

Templates read the validated config, so a renamed or removed field also breaks every template that uses it. Search for it with `grep -rn '<field>' template/config`.
