# Task completion

Pick the checks matching what changed:

- validate.py / plugin.py: `uv run --locked pytest template/scripts/test_validate.py -q`; if model changed, `just template schema` and commit the regenerated `cluster.schema.json`.
- Templates (`template/config/**`): `just configure` (needs `just init` + filled cluster.toml), then `oxfmt --check ./.sops.yaml ./bootstrap ./kubernetes ./talos`; bootstrap chart changes: `just template test-helmfile`. Don't commit rendered output or secrets unless deliberately moving past the template stage.
- Workflows: `zizmor --offline .github/workflows/*.yaml`.
- Formatting runs in lefthook pre-commit (oxfmt, just --fmt, mise fmt, mise lock); mise config edits require `mise lock`.
