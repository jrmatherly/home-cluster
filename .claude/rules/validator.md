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

Templates read the validated config, so a renamed or removed field also breaks every template that uses it. Search for it with `grep -rn '<field>' template/config`.
