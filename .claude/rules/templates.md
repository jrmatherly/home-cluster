---
paths:
    - "template/**"
    - "makejinja.toml"
---

# Editing makejinja templates

- `just configure` renders `template/config/**/*.j2` and `template/overrides/` into the repo root. Edit the `.j2` source. A hand edit to a rendered file is lost on the next render.
- The delimiters come from `makejinja.toml`: `#{ expr }#` for a variable, `#% stmt %#` for a block, and `#| ... #|` for a comment. Jinja leaves plain `{{ }}` alone, so topf Go templates (`{{ .Node.Host }}` in `*.tpl.j2`), Helm templates in chart values (`{{ .Release.Name }}`), and Flux substitutions (`${SECRET_DOMAIN}`) pass through to the output.
- `undefined = "strict"`, so a misspelled or missing variable fails the whole render.
- The template data is the validated `cluster.toml` from `validate.load()`, after defaults are applied. Use the computed fields instead of recomputing them: `cilium_bgp_enabled`, `hubble_enabled`, `controller_count`, `nvidia_enabled`, `postgres_backup_enabled`, `redis_enabled`, `observability_enabled`, `unifi_dns_enabled`, `unifi_dns_addr`, `pocket_id_enabled`, `radar_enabled`, `matherlynet_enabled`, `reactive_resume_enabled`, `kener_enabled`, `kener_smtp`, `network_optimizer_enabled`, `network_optimizer_oidc`, `pegaprox_enabled`, `pegaprox_metrics`, `actual_budget_enabled`, `cluster_issuer`, and `cert_sans`.
- `plugin.py` exposes these functions to templates: `age_key('public'|'private')`, `cloudflare_tunnel_id()`, `cloudflare_tunnel_secret()`, `deploy_key()`, and `webhook_token()`. Each one reads a gitignored secret file, so call them only inside `*.sops.*` templates, which `just configure` encrypts.
- Files named `*.partial.yaml.j2` are not rendered.
- CI runs `oxfmt --check` on the rendered output. Write templates so they render already formatted with 2-space indent. makejinja's `trim_blocks` and `lstrip_blocks` default to true, so a `#% %#` tag on its own line leaves no blank line in the output.
- The Stop hook in `.claude/settings.json` renders every fixture in `.github/template-tests/valid/`. When you add a branch that depends on config, make sure some fixture takes that branch, or add one to that directory and to the `validate-valid` job's matrix in `.github/workflows/template-e2e.yaml`.
