# Tech stack

- Tool versions pinned in `.mise/config.toml` (+ `.mise/conf.d/template.toml` for template-only tools uv/sd/taplo); lockfile `.mise/mise.lock` (multi-platform). mise env sets KUBECONFIG, SOPS_CONFIG, SOPS_AGE_KEY_FILE, TALOSCONFIG to repo-local paths.
- Python >=3.14 via uv (`pyproject.toml`, `package = false`, `uv.lock`): makejinja + pydantic v2 pinned exactly; pytest dev group. Python only exists for templating/validation.
- Task runner: just (modules via `mod`), logging via `gum log`.
- Cluster: Talos (talosctl, topf for config render/apply), Kubernetes, Flux (flux2 + flux-operator/flux-instance), helm/helmfile for bootstrap, kustomize, sops+age for secrets, Cilium, Envoy Gateway, cert-manager, cloudflared/cloudflare-dns, k8s-gateway, spegel.
- Validation: kubeconform (`template/resources/kubeconform.sh`), taplo (TOML vs schema), flate (Flux test in CI), zizmor (GH Actions audit).
- Formatting: oxfmt (JSON/YAML/Markdown, printWidth 100), `just --fmt`, `mise fmt`. Git hooks via lefthook (`.lefthook.toml`, installed by mise postinstall).
- Renovate (`.renovaterc.json5`, extends `home-operations/renovate-presets`, whose default scans `.yaml.j2` with the flux/kubernetes/helm-values managers); `# renovate:` comments only in `talos/topf.yaml.j2`.
