# Home cluster

A home Kubernetes cluster: Talos Linux nodes as VMs on three Proxmox hosts, Flux reconciling the
`kubernetes/` tree of this repository, and the apps that run there. The repository started from
[onedr0p/cluster-template](https://github.com/onedr0p/cluster-template) and keeps its shape: one
configuration file, `cluster.toml`, is rendered by [makejinja](https://github.com/mirkolenz/makejinja)
into the Talos, Kubernetes, Flux and bootstrap configuration, after
[pydantic](https://docs.pydantic.dev/) has validated and defaulted it.

The documentation lives in [`docs/`](./docs) and is served from the cluster itself. It describes the
hosts, the architecture, the decisions behind it and the runbooks, in placeholders rather than real
addresses, because this repository is public.

## What runs here

- **Platform:** Talos Linux, Cilium with BGP to the gateway, Flux, cert-manager, Envoy Gateway,
  external-dns for Cloudflare and for the UniFi console, a Cloudflare tunnel, spegel, reloader.
- **Storage:** `local-path` volumes pinned to a node, an NFS share from the media host through
  csi-driver-nfs, CloudNativePG for every Postgres with backups to object storage, one Redis per
  app that needs it, and RustFS as an in-cluster S3 store for app files.
- **Identity:** Pocket ID issues passkey logins, and apps without a login sit behind an Envoy
  Gateway security policy that signs users in with it.
- **Observability:** kube-prometheus-stack with Grafana and Alertmanager, InfluxDB for the
  Proxmox and network time series, Hubble.
- **Apps:** a media stack (Sonarr, Radarr, Prowlarr, SABnzbd, Recyclarr, Bazarr, Tautulli, Seerr,
  Maintainerr), Actual Budget, Kener, Network Optimizer, PegaProx, Radar, Reactive Resume, AI
  Workspace (with a browserless pod), AI KB, Langfuse for AI KB's traces, LocalAI on the GPU node (a
  chat and an embedding model), the public site, and this documentation.

Each app lives under `kubernetes/apps/<namespace>/<app>/`, rendered from its `.j2` source under
`template/config/`. `cluster.sample.toml` documents every setting, and a section in `cluster.toml`
turns the matching namespace on.

## How a change lands

1. Edit the `.j2` source under `template/config/`, never the rendered copy.
2. `just configure` renders everything, encrypts every `*.sops.*` file, runs kubeconform on
   `kubernetes/` and checks that topf can render `talos/`.
3. Commit and push. Flux reconciles `kubernetes/` from `main`, so the push is the deploy.

Node operations go through `just talos` (`status`, `drain`, `stop-node`, `reboot-node`, `resume`,
`health`, `upgrade-node`, `upgrade-k8s`), and `just kube` lists the Postgres primaries and
switches one over before a node is drained.

## Tooling

- [mise](https://mise.jdx.dev/) installs every pinned tool and points `KUBECONFIG`, `TALOSCONFIG`
  and the sops keys at files inside the repository. Run `mise trust` and `mise install` once.
- [lefthook](https://github.com/evilmartians/lefthook) runs the pre-commit checks: oxfmt on
  JSON, YAML, Markdown and TOML, `just --fmt`, `mise fmt`, `mise lock`, zizmor, Ruff, shellcheck,
  markdownlint, a scrub of the documentation pages for private values, and the cluster-guard
  tests when its files are staged.
- [Renovate](https://www.mend.io/renovate) keeps charts, images, tools and actions current, and
  pins the documentation image to its digest after every build.
- GitHub Actions build the documentation image and the model images for LocalAI. The
  template's fixture tests run locally through a Stop hook; the upstream CI jobs skip on this
  fork.

## Layout

```text
cluster.sample.toml   every setting, documented; cluster.toml is the gitignored real one
template/config/      the .j2 sources for bootstrap/, kubernetes/ and talos/
template/scripts/     the pydantic model of cluster.toml and its tests
kubernetes/           rendered Flux tree, reconciled from main
talos/                rendered Talos machine configuration (topf)
bootstrap/            rendered helmfile for the first install
docs/                 the documentation site (Nimbus on Astro) and its Dockerfile
images/               recipes for the model images LocalAI mounts
.github/              workflows, label and release-note config, and the template's test fixtures
```

## Private files

`cluster.toml`, `age.key`, `deploy.key`, `cloudflare-tunnel.json`, `flux-webhook-token.txt`,
`kubeconfig`, `talos/talosconfig` and the `private/` directory are gitignored and never leave this
machine. Every file with `.sops.` in its name is encrypted before it is committed.

## License

MIT, inherited from the upstream template. See [LICENSE](./LICENSE).
