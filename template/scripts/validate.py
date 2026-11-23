"""Validate cluster.toml, apply defaults, and emit the config as JSON.

Standalone usage (doctor, CI): uv run --locked --no-dev template/scripts/validate.py [cluster.toml]
Schema export (just template schema): uv run --locked --no-dev template/scripts/validate.py --schema
In-process usage (makejinja plugin): from validate import load

Exits non-zero with one human-readable error per line on stderr when the
config is invalid.
"""

import json
import re
import sys
import tomllib
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    model_validator,
)

# Git hosts whose SSH host keys are bundled with the template; ssh:// URLs
# pointing anywhere else must provide repository.known_hosts.
KNOWN_SSH_HOSTS = ["github.com", "gitlab.com", "codeberg.org"]

REPO_URL_PATTERN = r"^(https?://|ssh://git@)[^/]+/.+$"
FQDN_PATTERN = r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"


def _network(value: Any) -> Any:
    """Parse a CIDR, requiring network-address form (no host bits set)."""
    if not isinstance(value, str):
        return value
    try:
        return IPv4Network(value)
    except ValueError:
        try:
            fixed = IPv4Network(value, strict=False)
        except ValueError:
            raise ValueError(f"{value!r} is not a valid IPv4 CIDR") from None
        raise ValueError(f"{value!r} has host bits set; did you mean {fixed}?") from None


def _asn(value: str) -> str:
    if value == "":
        return value
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError(f"{value!r} must be a decimal ASN")
    if not 1 <= int(value) <= 4294967295:
        raise ValueError(f"{value!r} must be in the range 1-4294967295")
    return value


type Cidr = Annotated[IPv4Network, BeforeValidator(_network)]
type Asn = Annotated[str, AfterValidator(_asn)]
type Fqdn = Annotated[str, Field(pattern=FQDN_PATTERN)]
# An address with none of the characters a double-quoted YAML string or a Flux
# substitution would change.
_SAFE = r'[^\s"\\$,@]+'
EMAIL = rf"{_SAFE}@{_SAFE}\.{_SAFE}"
type EmailAddress = Annotated[str, Field(pattern=f"^{EMAIL}$")]
# A [[nodes]] name that _worker checks against the node list.
type WorkerName = Annotated[str, Field(pattern=r"^[a-z0-9-]*$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Reject a section where only some of the fields in names are set.
def _all_or_none(model: Model, label: str, names: tuple[str, ...]) -> None:
    unset = [name for name in names if not getattr(model, name)]
    if unset and len(unset) < len(names):
        raise ValueError(
            f"{label} is partially configured: set {', '.join(names[:-1])} and "
            f"{names[-1]} together (missing: {', '.join(unset)})"
        )


class Network(Model):
    node_cidr: Cidr
    dns_servers: list[IPv4Address] = [IPv4Address("1.1.1.1"), IPv4Address("1.0.0.1")]
    ntp_servers: list[IPv4Address] = [IPv4Address("162.159.200.1"), IPv4Address("162.159.200.123")]
    # The first IP in node_cidr unless set explicitly.
    default_gateway: IPv4Address = Field(
        default_factory=lambda data: data["node_cidr"].network_address + 1
    )
    vlan_tag: str | None = Field(default=None, pattern=r"^[0-9]+$")

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.default_gateway not in self.node_cidr:
            raise ValueError(
                f"default_gateway {self.default_gateway} is not inside node_cidr {self.node_cidr}"
            )
        if self.vlan_tag is not None and not 1 <= int(self.vlan_tag) <= 4094:
            raise ValueError(f"vlan_tag {self.vlan_tag} must be in the range 1-4094")
        return self


class Api(Model):
    addr: IPv4Address
    tls_sans: list[Fqdn] | None = None


class Kubernetes(Model):
    pod_cidr: Cidr = IPv4Network("10.42.0.0/16")
    svc_cidr: Cidr = IPv4Network("10.43.0.0/16")
    # The 10th IP in svc_cidr unless set explicitly.
    coredns_addr: IPv4Address = Field(
        default_factory=lambda data: data["svc_cidr"].network_address + 10
    )
    api: Api

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.coredns_addr not in self.svc_cidr:
            raise ValueError(
                f"coredns_addr {self.coredns_addr} is not inside svc_cidr {self.svc_cidr}"
            )
        return self


class Gateways(Model):
    internal: IPv4Address
    dns: IPv4Address
    # Required when ingress.mode is not "none".
    external: IPv4Address | None = None


class Repository(Model):
    url: str = Field(pattern=REPO_URL_PATTERN)
    branch: str = Field(default="main", min_length=1)
    webhook_provider: Literal["github", "gitlab", "generic-hmac", "none"] = "github"
    known_hosts: str = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.url.startswith("ssh://"):
            host = self.url.removeprefix("ssh://git@").split("/", 1)[0].split(":", 1)[0]
            if host not in KNOWN_SSH_HOSTS and not self.known_hosts:
                raise ValueError(
                    f"known_hosts is required for ssh:// URLs to {host!r} "
                    f"(host keys are only bundled for {', '.join(KNOWN_SSH_HOSTS)})"
                )
        return self


class Onepassword(Model):
    vault: str = Field(default="", pattern=r"^[A-Za-z0-9_-]*$")


class Domain(Model):
    name: Fqdn


class Dns(Model):
    provider: Literal["cloudflare", "none"] = "cloudflare"


class Ingress(Model):
    mode: Literal["cloudflare-tunnel", "direct", "none"] = "cloudflare-tunnel"
    # The Cloudflare tunnel's ID, which is public: external.<domain> is a CNAME to it.
    tunnel_id: str = Field(default="", pattern=r"^[A-Za-z0-9-]*$")


class Bgp(Model):
    router_addr: IPv4Address | Literal[""] = ""
    router_asn: Asn = ""
    node_asn: Asn = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        unset = [
            name for name in ("router_addr", "router_asn", "node_asn") if getattr(self, name) == ""
        ]
        if unset and len(unset) < 3:
            raise ValueError(
                "bgp is partially configured: set router_addr, router_asn and "
                f"node_asn together (missing: {', '.join(unset)})"
            )
        return self


class Talos(Model):
    # Default Image Factory schematic for nodes that don't set their own.
    schematic_id: str | None = Field(default=None, pattern=r"^[a-z0-9]{64}$")


class Spegel(Model):
    # True when the cluster has more than one node, unless set explicitly.
    enabled: bool | None = None


class Hubble(Model):
    # The OIDC client created for the Hubble UI in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")


class Cilium(Model):
    loadbalancer_mode: Literal["dsr", "snat"] = "dsr"
    bgp: Bgp = Bgp()
    hubble: Hubble = Hubble()


class PostgresBackup(Model):
    # S3 API endpoint of the object store, without a path.
    endpoint: str = Field(default="", pattern=r"^(https://[^/\s]+)?$")
    bucket: str = Field(default="", pattern=r"^([a-z0-9][a-z0-9.-]*[a-z0-9])?$")

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "backup", ("endpoint", "bucket"))
        return self


class Postgres(Model):
    backup: PostgresBackup = PostgresBackup()


class EtcdBackup(Model):
    enabled: bool = False


class VolumeBackup(Model):
    enabled: bool = False


class Redis(Model):
    # Gives every app that includes the redis component a Redis of its own.
    enabled: bool = False


class LocalAi(Model):
    # The OIDC client created for the LocalAI WebUI in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")


class Observability(Model):
    enabled: bool = False
    # Alertmanager sends alerts to the Discord webhook in the vault. Off, every alert
    # goes to the null receiver.
    discord: bool = False
    # Alertmanager pings the heartbeat URL in the vault with the Watchdog alert, so a
    # dead Prometheus, Alertmanager or node is noticed. It is a second receiver beside
    # Discord and does not detect a broken Discord webhook.
    heartbeat: bool = False
    # The OIDC client created for Grafana in the Pocket ID admin UI.
    grafana_oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    # Grafana encrypts its stored data source secrets with the key in the vault
    # instead of its built-in default. Never turn it off or change the key without
    # reprovisioning.
    secret_key: bool = False
    # A GitHub App for Grafana's GitHub data source.
    github_app_id: str = Field(default="", pattern=r"^[0-9]*$")
    github_app_installation_id: str = Field(default="", pattern=r"^[0-9]*$")
    # The organization Grafana's Sentry data source reads.
    sentry_org: str = Field(default="", pattern=r"^[a-z0-9-]*$")
    # Regional organizations use their region's host.
    sentry_url: str = Field(default="https://sentry.io", pattern=r"^https://[^/\s]+$")
    # Proxmox hosts running prometheus-node-exporter, scraped on port 9100.
    proxmox_hosts: list[IPv4Address] = []

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.heartbeat and not self.discord:
            raise ValueError(
                "heartbeat requires discord: the heartbeat is a second receiver beside Discord"
            )
        _all_or_none(self, "observability", ("github_app_id", "github_app_installation_id"))
        if not self.enabled:
            for name in (
                "discord",
                "grafana_oidc_client_id",
                "secret_key",
                "github_app_id",
                "sentry_org",
                "proxmox_hosts",
            ):
                if getattr(self, name):
                    raise ValueError(
                        f"{name} requires enabled: it only runs with the rest of the stack"
                    )
        return self


class Unifi(Model):
    # Address of the UniFi console, without a path.
    host: str = Field(default="", pattern=r"^(https://[^/\s]+)?$")


class PocketId(Model):
    enabled: bool = False
    # Also attaches the route to the external gateway, so the internet reaches it.
    public: bool = False


class Radar(Model):
    # The OIDC client created for Radar in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")


class Matherlynet(Model):
    enabled: bool = False
    # The site sends mail through the SMTP URL in the vault. Off, it sends none.
    smtp: bool = False
    # The site's mail carries the sender address in the vault.
    mail: bool = False
    # OAuth apps for signing in with GitHub or Google. Each flag says the app's
    # secret is in the vault.
    github_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    github: bool = False
    google_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    google: bool = False
    # Lets the site call the in-cluster LocalAI.
    playground: bool = False

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "matherlynet", ("github_client_id", "github"))
        _all_or_none(self, "matherlynet", ("google_client_id", "google"))
        if not self.enabled:
            for name in ("smtp", "mail", "github_client_id", "google_client_id", "playground"):
                if getattr(self, name):
                    raise ValueError(
                        f"{name} requires enabled: the site only runs when it is enabled"
                    )
        return self


class ReactiveResume(Model):
    enabled: bool = False
    # The OIDC client created for Reactive Resume in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    # The bucket that holds uploads. Its endpoint and key pair are in the vault.
    s3_bucket: str = Field(default="", pattern=r"^([a-z0-9][a-z0-9.-]*[a-z0-9])?$")

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "reactive_resume", ("enabled", "oidc_client_id", "s3_bucket"))
        return self


class Kener(Model):
    enabled: bool = False
    # Kener sends mail with the SMTP settings and the sender address in the vault.
    smtp: bool = False

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.smtp and not self.enabled:
            raise ValueError("smtp requires enabled: Kener only runs when it is enabled")
        return self


class NetworkOptimizer(Model):
    enabled: bool = False
    # The OIDC client created for Network Optimizer in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.oidc_client_id and not self.enabled:
            raise ValueError(
                "oidc_client_id requires enabled: Network Optimizer only runs when it is enabled"
            )
        return self


class PegaProx(Model):
    enabled: bool = False
    # Prometheus scrapes /api/metrics with the API token in the vault.
    metrics: bool = False

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.metrics and not self.enabled:
            raise ValueError("metrics requires enabled: PegaProx only runs when it is enabled")
        return self


class ActualBudget(Model):
    # The OIDC client created for Actual Budget in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    # Also attaches the route to the external gateway, so the internet reaches it.
    public: bool = False


class Media(Model):
    # The Proxmox host that exports the media tree. Set it to enable the stack.
    nfs_server: IPv4Address | Literal[""] = ""
    nfs_share: str = Field(default="/srv/media", pattern=r'^/[^"\\\s$]*$')
    # The worker whose Proxmox host serves the export.
    node: WorkerName = ""
    timezone: str = Field(default="Etc/UTC", pattern=r"^[A-Za-z0-9_+/-]+$")
    # The OIDC client created in the Pocket ID admin UI for the gateway sign-in.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    recyclarr: bool = False
    plex_host: IPv4Address | Literal[""] = ""
    # Also attaches every app's UI route to the external gateway, so the internet reaches it.
    public: bool = False
    # Raise it after changing a media key or the Plex token in the vault: the
    # HelmReleases that carry it are upgraded, and their configure hooks push the
    # new keys into the apps.
    keys_revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.nfs_server == "":
            for name, field in type(self).model_fields.items():
                if name != "nfs_server" and getattr(self, name) != field.default:
                    raise ValueError(
                        f"{name} requires nfs_server: the media stack only runs when "
                        "the export is set"
                    )
        elif not (self.node and self.oidc_client_id):
            raise ValueError("media requires node and oidc_client_id")
        return self


# Server env vars the AI Workspace templates set or depend on (the port and mode
# the probes and Service assume).
AI_WORKSPACE_OWNED_ENV = (
    "LOCALAI_API_HOST",
    "LOCALAI_API_KEY",
    "POSTGRES_PRISMA_URL",
    "POSTGRES_URL_NON_POOLING",
    "PORT",
    "NODE_ENV",
    "AUTH_SECRET",
    "AUTH_URL",
    "AUTH_OIDC_ISSUER",
    "AUTH_OIDC_CLIENT_ID",
    "AUTH_OIDC_CLIENT_SECRET",
    "AUTH_ALLOWED_EMAILS",
    "AUTH_ADMIN_EMAILS",
    "PUPPETEER_WSS_ENDPOINT",
    "BROWSERLESS_TOKEN",
)


class AiWorkspace(Model):
    # The OIDC client created in the Pocket ID admin UI for the app's own sign-in.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    # Only the addresses and @domain rules in the vault may sign in. Off, every
    # Pocket ID user may.
    allowlist: bool = False
    # The addresses in the vault are admins.
    admins: bool = False
    # Runs the Browsing pod, with the browserless token in the vault.
    browsing: bool = False
    # Also attaches the route to the external gateway, so the internet reaches it.
    public: bool = False
    # Names of the extra server env vars, such as vendor API keys, whose values are
    # in the vault item `ai-workspace-env`.
    env_keys: list[Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")]] = []

    @model_validator(mode="after")
    def check(self) -> Self:
        if len(set(self.env_keys)) != len(self.env_keys):
            raise ValueError("ai_workspace.env_keys: a name is listed twice")
        for key in self.env_keys:
            if key in AI_WORKSPACE_OWNED_ENV:
                raise ValueError(
                    f"ai_workspace.env_keys: {key} belongs to the templates and cannot "
                    "be overridden"
                )
        return self


class AiKb(Model):
    enabled: bool = False
    # Promoted to system administrator at startup once that account exists.
    admin_email: EmailAddress = ""
    # The OIDC client created for AI KB in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    # Stores files in RustFS with the app's own key pair from the vault; the
    # provisioning Job scopes the pair to the ai-kb-files bucket.
    rustfs: bool = False
    # Sends traces to Langfuse. AI KB wraps its chat, embedding, rerank, VLM and ASR models and its
    # knowledge ingest and post-process paths in Langfuse tracers, so traces carry full prompts and
    # answers and the chunk text of every ingested document.
    tracing: bool = False
    # Turns on the chart's Neo4j for GraphRAG.
    neo4j: bool = False
    # Turns on the internal SearXNG instance for web search.
    searxng: bool = False

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "ai_kb", ("enabled", "admin_email"))
        for field in ("oidc_client_id", "rustfs", "tracing", "neo4j", "searxng"):
            if getattr(self, field) and not self.enabled:
                raise ValueError(f"ai_kb.{field} requires the rest of [ai_kb]")
        return self


class RustFs(Model):
    enabled: bool = False
    # The worker whose local-path volume holds every object.
    node: WorkerName = ""
    # Raise it after changing a consumer's key pair in the vault, so the
    # provisioning Job is recreated and runs again.
    keys_revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "rustfs", ("enabled", "node"))
        return self


class Langfuse(Model):
    enabled: bool = False
    # The OIDC client created for Langfuse in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "langfuse", ("enabled", "oidc_client_id"))
        return self


class Itsaplan(Model):
    enabled: bool = False


class CliProxyApi(Model):
    enabled: bool = False
    # Deploys Oh-My-CPA, the second console, with its master key from the vault.
    ohmycpa: bool = False
    # The seed config carries the GitHub token in the vault, for the plugin store's
    # release lookups.
    github: bool = False

    @model_validator(mode="after")
    def check(self) -> Self:
        for name in ("ohmycpa", "github"):
            if getattr(self, name) and not self.enabled:
                raise ValueError(f"cliproxyapi.{name} needs enabled")
        return self


class CareerOps(Model):
    enabled: bool = False
    # The Pocket ID client the gateway signs dashboard users in with
    # (callback https://career.<domain>/oauth2/callback).
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    # Which Claude credential the pod reads from the vault: the OAuth token from
    # `claude setup-token`, or the client key it sends to anthropic_base_url.
    claude_credential: Literal["oauth", "proxy"] = "oauth"
    # The in-cluster CLIProxyAPI Service the pod's Claude CLI calls instead of
    # Anthropic, with no /v1 (http://cliproxyapi.llms.svc.cluster.local:8317).
    anthropic_base_url: str = Field(default="", pattern=r"^(https?://\S*[^/\s])?$")
    # The second Pocket ID client, for the publish account page
    # (callback https://cv.<domain>/api/auth/callback/pocket-id).
    publish_oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    # The dashboard's share features use the API key in the vault, minted on the
    # publish account page after the first deploy.
    publish: bool = False
    # Also attach the dashboard route to the external gateway.
    public: bool = False

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "career_ops", ("enabled", "oidc_client_id", "publish_oidc_client_id"))
        if not self.enabled:
            for name in ("publish", "anthropic_base_url"):
                if getattr(self, name):
                    raise ValueError(
                        f"career_ops.{name} requires enabled: career-ops only runs when "
                        "it is enabled"
                    )
        if (self.claude_credential == "proxy") != bool(self.anthropic_base_url):
            raise ValueError("claude_credential 'proxy' and anthropic_base_url are set together")
        return self


class Node(Model):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]{0,61}[a-z0-9]$|^[a-z0-9]$")
    address: IPv4Address
    controller: bool
    disk: str
    mac_addr: str = Field(pattern=r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")
    # Falls back to talos.schematic_id when unset.
    schematic_id: str | None = Field(default=None, pattern=r"^[a-z0-9]{64}$")
    mtu: int = Field(default=1500, ge=1450, le=9000)
    secureboot: bool = False
    encrypt_disk: bool = False
    kernel_modules: list[str] = []

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.name in ("global", "controller", "worker"):
            raise ValueError(f"node name {self.name!r} is reserved")
        return self


class GithubRunner(Model):
    # Registers the in-cluster Actions runner scale set with the token in the vault.
    enabled: bool = False


class Config(Model):
    model_config = ConfigDict(extra="forbid", title="cluster.toml")

    network: Network
    kubernetes: Kubernetes
    gateways: Gateways
    repository: Repository
    onepassword: Onepassword = Onepassword()
    domain: Domain
    dns: Dns
    # Defaults to "cloudflare-tunnel" when dns.provider is "cloudflare",
    # otherwise "none".
    ingress: Ingress = Field(
        default_factory=lambda data: Ingress(
            mode="cloudflare-tunnel" if data["dns"].provider == "cloudflare" else "none"
        )
    )
    cilium: Cilium = Cilium()
    talos: Talos = Talos()
    spegel: Spegel = Spegel()
    postgres: Postgres = Postgres()
    etcd_backup: EtcdBackup = EtcdBackup()
    volume_backup: VolumeBackup = VolumeBackup()
    redis: Redis = Redis()
    observability: Observability = Observability()
    unifi: Unifi = Unifi()
    pocket_id: PocketId = PocketId()
    radar: Radar = Radar()
    matherlynet: Matherlynet = Matherlynet()
    reactive_resume: ReactiveResume = ReactiveResume()
    kener: Kener = Kener()
    network_optimizer: NetworkOptimizer = NetworkOptimizer()
    pegaprox: PegaProx = PegaProx()
    actual_budget: ActualBudget = ActualBudget()
    media: Media = Media()
    ai_workspace: AiWorkspace = AiWorkspace()
    ai_kb: AiKb = AiKb()
    rustfs: RustFs = RustFs()
    langfuse: Langfuse = Langfuse()
    itsaplan: Itsaplan = Itsaplan()
    cliproxyapi: CliProxyApi = CliProxyApi()
    career_ops: CareerOps = CareerOps()
    localai: LocalAi = LocalAi()
    github_runner: GithubRunner = GithubRunner()
    nodes: list[Node]

    @computed_field
    @property
    def cilium_bgp_enabled(self) -> bool:
        bgp = self.cilium.bgp
        return bgp.router_addr != "" and bgp.router_asn != "" and bgp.node_asn != ""

    @computed_field
    @property
    def onepassword_enabled(self) -> bool:
        return self.onepassword.vault != ""

    # The UI has no login of its own, so Hubble is only turned on when its gateway login exists.
    @computed_field
    @property
    def hubble_enabled(self) -> bool:
        return self.cilium.hubble.oidc_client_id != ""

    # The WebUI is only turned on behind the gateway's Pocket ID login.
    @computed_field
    @property
    def localai_webui_enabled(self) -> bool:
        return self.localai.oidc_client_id != ""

    # Replica counts for control-plane-only workloads key off this rather
    # than len(nodes); a cluster can have many workers but one controller.
    @computed_field
    @property
    def controller_count(self) -> int:
        return sum(1 for node in self.nodes if node.controller)

    # True when a node loads the NVIDIA kernel module; gates the device plugin.
    @computed_field
    @property
    def nvidia_enabled(self) -> bool:
        return any("nvidia" in node.kernel_modules for node in self.nodes)

    @computed_field
    @property
    def postgres_backup_enabled(self) -> bool:
        return self.postgres.backup.endpoint != ""

    @computed_field
    @property
    def etcd_backup_enabled(self) -> bool:
        return self.etcd_backup.enabled

    @computed_field
    @property
    def volume_backup_enabled(self) -> bool:
        return self.volume_backup.enabled

    # Gates components/redis, which gives an app that includes it a Redis of its own.
    @computed_field
    @property
    def redis_enabled(self) -> bool:
        return self.redis.enabled

    # Gates the observability namespace.
    @computed_field
    @property
    def observability_enabled(self) -> bool:
        return self.observability.enabled

    # Gates the ExternalDNS instance that writes internal names to the UniFi console.
    @computed_field
    @property
    def unifi_dns_enabled(self) -> bool:
        return self.unifi.host != ""

    # The console's address when unifi.host is an IPv4 address, otherwise empty.
    # Cluster DNS forwards the domain's lookups to it, because unifi-dns writes
    # the names that exist only on the internal gateway there.
    @computed_field
    @property
    def unifi_dns_addr(self) -> str:
        host = self.unifi.host.removeprefix("https://").partition(":")[0]
        try:
            return str(IPv4Address(host))
        except ValueError:
            return ""

    # Gates Pocket ID, the identity provider, and its database.
    @computed_field
    @property
    def pocket_id_enabled(self) -> bool:
        return self.pocket_id.enabled

    # Gates Radar. The client is created in Pocket ID first, so its ID being set
    # means the login Radar is served behind already exists.
    @computed_field
    @property
    def radar_enabled(self) -> bool:
        return self.radar.oidc_client_id != ""

    # Gates the matherlynet website and its database.
    @computed_field
    @property
    def matherlynet_enabled(self) -> bool:
        return self.matherlynet.enabled

    # Gates Reactive Resume and its database.
    @computed_field
    @property
    def reactive_resume_enabled(self) -> bool:
        return self.reactive_resume.enabled

    # Gates Kener and its database.
    @computed_field
    @property
    def kener_enabled(self) -> bool:
        return self.kener.enabled

    # Adds the mail settings to Kener's Secret.
    @computed_field
    @property
    def kener_smtp(self) -> bool:
        return self.kener.smtp

    # Gates Network Optimizer.
    @computed_field
    @property
    def network_optimizer_enabled(self) -> bool:
        return self.network_optimizer.enabled

    # Adds the Pocket ID sign-in to Network Optimizer.
    @computed_field
    @property
    def network_optimizer_oidc(self) -> bool:
        return self.network_optimizer.oidc_client_id != ""

    # Gates PegaProx.
    @computed_field
    @property
    def pegaprox_enabled(self) -> bool:
        return self.pegaprox.enabled

    # Adds the Prometheus scrape and the Grafana dashboard for PegaProx.
    @computed_field
    @property
    def pegaprox_metrics(self) -> bool:
        return self.pegaprox.metrics

    # Gates Actual Budget. The client is created in Pocket ID first, so its ID
    # being set means the login it is served behind already exists.
    @computed_field
    @property
    def actual_budget_enabled(self) -> bool:
        return self.actual_budget.oidc_client_id != ""

    @computed_field
    @property
    def media_enabled(self) -> bool:
        return self.media.nfs_server != ""

    # Gates Tautulli, Seerr and Maintainerr, which do nothing without Plex.
    @computed_field
    @property
    def media_plex_enabled(self) -> bool:
        return self.media_enabled and self.media.plex_host != ""

    # Gates AI Workspace. The client is created in Pocket ID first, so its ID
    # being set means the login it is served behind already exists.
    @computed_field
    @property
    def ai_workspace_enabled(self) -> bool:
        return self.ai_workspace.oidc_client_id != ""

    # Gates AI KB and its database.
    @computed_field
    @property
    def ai_kb_enabled(self) -> bool:
        return self.ai_kb.enabled

    @computed_field
    @property
    def ai_kb_oidc(self) -> bool:
        return self.ai_kb.oidc_client_id != ""

    @computed_field
    @property
    def ai_kb_rustfs(self) -> bool:
        return self.ai_kb.rustfs

    @computed_field
    @property
    def ai_kb_tracing(self) -> bool:
        return self.ai_kb.tracing

    @computed_field
    @property
    def ai_kb_neo4j(self) -> bool:
        return self.ai_kb.neo4j

    @computed_field
    @property
    def ai_kb_searxng(self) -> bool:
        return self.ai_kb.searxng

    @computed_field
    @property
    def rustfs_enabled(self) -> bool:
        return self.rustfs.enabled

    @computed_field
    @property
    def langfuse_enabled(self) -> bool:
        return self.langfuse.enabled

    @computed_field
    @property
    def itsaplan_enabled(self) -> bool:
        return self.itsaplan.enabled

    @computed_field
    @property
    def cliproxyapi_enabled(self) -> bool:
        return self.cliproxyapi.enabled

    @computed_field
    @property
    def ohmycpa_enabled(self) -> bool:
        return self.cliproxyapi.ohmycpa

    # Gates the career-ops namespace: the dashboard and the publish service.
    @computed_field
    @property
    def career_ops_enabled(self) -> bool:
        return self.career_ops.enabled

    @computed_field
    @property
    def github_runner_enabled(self) -> bool:
        return self.github_runner.enabled

    # One bucket and one key pair scoped to it per app; the provisioning Job creates them.
    @computed_field
    @property
    def rustfs_consumers(self) -> list[dict[str, str]]:
        buckets = {
            "ai-kb": (self.ai_kb_rustfs, "ai-kb-files"),
            "langfuse": (self.langfuse_enabled, "langfuse-events"),
            "itsaplan": (self.itsaplan_enabled, "itsaplan-attachments"),
        }
        return [{"name": name, "bucket": bucket} for name, (on, bucket) in buckets.items() if on]

    @computed_field
    @property
    def cluster_issuer(self) -> str:
        if self.dns.provider == "cloudflare":
            return "letsencrypt-production"
        return "internal-ca"

    # Never a destination for an egress fence that admits only public addresses: the
    # RFC 1918, CGNAT and link-local ranges plus the cluster's own pod, service and node ranges.
    @computed_field
    @property
    def private_cidrs(self) -> list[str]:
        return [
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "100.64.0.0/10",
            "169.254.0.0/16",
            # Loopback, "this" network, IETF protocol assignments, benchmarking, multicast, reserved.
            "127.0.0.0/8",
            "0.0.0.0/8",
            "192.0.0.0/24",
            "198.18.0.0/15",
            "224.0.0.0/4",
            "240.0.0.0/4",
            str(self.kubernetes.pod_cidr),
            str(self.kubernetes.svc_cidr),
            str(self.network.node_cidr),
        ]

    # Single source for the machine and apiServer certificate SAN lists,
    # which live in separate patch files.
    @computed_field
    @property
    def cert_sans(self) -> list[str]:
        return ["127.0.0.1", str(self.kubernetes.api.addr), *(self.kubernetes.api.tls_sans or [])]

    def _worker(self, label: str, name: str) -> None:
        if not any(node.name == name and not node.controller for node in self.nodes):
            raise ValueError(f"{label} {name} must name a [[nodes]] entry with controller = false")

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.spegel.enabled is None:
            self.spegel.enabled = len(self.nodes) > 1
        for i, node in enumerate(self.nodes):
            if node.schematic_id is None:
                node.schematic_id = self.talos.schematic_id
            if node.schematic_id is None:
                raise ValueError(
                    f"nodes[{i}].schematic_id is required: set it on the node "
                    "or set a cluster-wide default in [talos]"
                )
        if self.ingress.mode != "none" and self.dns.provider != "cloudflare":
            raise ValueError(
                f"ingress.mode {self.ingress.mode!r} requires dns.provider 'cloudflare'"
            )
        if self.ingress.mode != "none" and self.gateways.external is None:
            raise ValueError(
                f"gateways.external is required when ingress.mode is {self.ingress.mode!r}"
            )
        if self.ingress.mode == "cloudflare-tunnel" and not self.ingress.tunnel_id:
            raise ValueError(
                "ingress.tunnel_id is required when ingress.mode is 'cloudflare-tunnel'"
            )
        if self.etcd_backup_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "etcd_backup requires postgres.backup: its endpoint is where the snapshots go"
            )
        if self.volume_backup_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "volume_backup requires postgres.backup: its endpoint is where the backups go"
            )
        if self.pocket_id_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "pocket_id requires postgres.backup: its database holds passkeys and "
                "signing keys, which cannot be recreated"
            )
        if self.pocket_id.public and not self.pocket_id_enabled:
            raise ValueError(
                "pocket_id.public requires pocket_id.enabled: Pocket ID only runs when it is enabled"
            )
        if self.pocket_id.public and self.ingress.mode == "none":
            raise ValueError(
                "pocket_id.public requires ingress.mode other than 'none': there is no "
                "external gateway to attach it to"
            )
        if self.radar_enabled and not self.pocket_id_enabled:
            raise ValueError("radar requires pocket_id: Pocket ID is Radar's only login")
        if self.hubble_enabled and not self.pocket_id_enabled:
            raise ValueError(
                "cilium.hubble requires pocket_id: Pocket ID is the Hubble UI's only login"
            )
        if self.observability.grafana_oidc_client_id and not self.pocket_id_enabled:
            raise ValueError(
                "observability.grafana_oidc_client_id requires pocket_id: "
                "Pocket ID is the OIDC provider Grafana signs in with"
            )
        if self.matherlynet_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "matherlynet requires postgres.backup: its database holds accounts, "
                "which cannot be recreated"
            )
        if self.matherlynet_enabled and self.ingress.mode != "cloudflare-tunnel":
            raise ValueError(
                "matherlynet requires ingress.mode 'cloudflare-tunnel': the site trusts "
                "the client address header Cloudflare sets"
            )
        if self.reactive_resume_enabled and not self.pocket_id_enabled:
            raise ValueError(
                "reactive_resume requires pocket_id: Pocket ID is Reactive Resume's only login"
            )
        if self.reactive_resume_enabled and self.ingress.mode == "none":
            raise ValueError(
                "reactive_resume requires ingress.mode other than 'none': it is served on "
                "the external gateway"
            )
        if self.kener_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "kener requires postgres.backup: its database holds monitors, incidents "
                "and accounts, which cannot be recreated"
            )
        if self.kener_enabled and not self.redis_enabled:
            raise ValueError("kener requires redis: Kener's job queue lives in Redis")
        if self.kener_enabled and self.ingress.mode == "none":
            raise ValueError(
                "kener requires ingress.mode other than 'none': the status page is served "
                "on the external gateway"
            )
        if self.actual_budget_enabled and not self.pocket_id_enabled:
            raise ValueError(
                "actual_budget requires pocket_id: Pocket ID is Actual Budget's only login"
            )
        if self.actual_budget.public and not self.actual_budget_enabled:
            raise ValueError(
                "actual_budget.public requires oidc_client_id: Actual Budget only runs "
                "when the client is set"
            )
        # pocket_id.public already requires an ingress, so no separate ingress check.
        if self.actual_budget.public and not self.pocket_id.public:
            raise ValueError(
                "actual_budget.public requires pocket_id.public: a visitor from the internet "
                "must reach the Pocket ID login"
            )
        if self.ai_workspace_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "ai_workspace requires postgres.backup: its database is backed up there"
            )
        if self.ai_workspace_enabled and not self.pocket_id_enabled:
            raise ValueError("ai_workspace requires pocket_id: Pocket ID is its only login")
        for name in ("allowlist", "admins", "browsing", "public", "env_keys"):
            if getattr(self.ai_workspace, name) and not self.ai_workspace_enabled:
                raise ValueError(
                    f"ai_workspace.{name} requires oidc_client_id: AI Workspace only runs "
                    "when the client is set"
                )
        # pocket_id.public already requires an ingress, so no separate ingress check.
        if self.ai_workspace.public and not self.pocket_id.public:
            raise ValueError(
                "ai_workspace.public requires pocket_id.public: a visitor from the internet "
                "must reach the Pocket ID login"
            )
        if self.ai_kb_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "ai_kb requires postgres.backup: its database holds the knowledge bases, "
                "which cannot be recreated"
            )
        if self.ai_kb_enabled and not self.redis_enabled:
            raise ValueError("ai_kb requires redis: AI KB's task queue and streams live in Redis")
        if self.ai_kb_oidc and not self.pocket_id_enabled:
            raise ValueError(
                "ai_kb.oidc_client_id requires pocket_id: Pocket ID is the OIDC provider AI KB "
                "signs in with"
            )
        if self.ai_kb_enabled and self.ingress.mode == "none":
            raise ValueError(
                "ai_kb requires ingress.mode other than 'none': it is served on the "
                "external gateway"
            )
        if self.media_enabled and not self.pocket_id_enabled:
            raise ValueError("media requires pocket_id: the gateway sign-in is the only login")
        if self.media_enabled:
            self._worker("media.node", self.media.node)
        # pocket_id.public already requires an ingress, so no separate ingress check.
        if self.media.public and not self.pocket_id.public:
            raise ValueError(
                "media.public requires pocket_id.public: a visitor from the internet "
                "must reach the Pocket ID login"
            )
        if self.rustfs_enabled:
            self._worker("rustfs.node", self.rustfs.node)
        if self.ai_kb_tracing and not self.langfuse_enabled:
            raise ValueError("ai_kb.tracing requires langfuse: the traces are sent there")
        if self.ai_kb_rustfs and not self.rustfs_enabled:
            raise ValueError("ai_kb.rustfs requires rustfs: the bucket lives there")
        # pocket_id already requires postgres.backup, so no separate backup check.
        if self.langfuse_enabled and not self.redis_enabled:
            raise ValueError("langfuse requires redis: Langfuse's queues live in Redis")
        if self.langfuse_enabled and not self.pocket_id_enabled:
            raise ValueError(
                "langfuse.oidc_client_id requires pocket_id: Pocket ID is Langfuse's only login"
            )
        if self.langfuse_enabled and not self.rustfs_enabled:
            raise ValueError(
                "langfuse requires rustfs: Langfuse writes every event to its bucket there"
            )
        if self.itsaplan_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "itsaplan requires postgres.backup: its database is a CloudNativePG cluster "
                "backed up there"
            )
        if self.itsaplan_enabled and not self.rustfs_enabled:
            raise ValueError("itsaplan requires rustfs: attachments are stored in its bucket there")
        if self.career_ops_enabled and not self.pocket_id_enabled:
            raise ValueError(
                "career_ops requires pocket_id: Pocket ID is the dashboard's only login"
            )
        if self.career_ops_enabled and self.ingress.mode != "cloudflare-tunnel":
            raise ValueError(
                "career_ops requires ingress.mode 'cloudflare-tunnel': the publish service "
                "trusts the client address header Cloudflare sets"
            )
        if self.career_ops_enabled and not self.volume_backup_enabled:
            raise ValueError(
                "career_ops requires volume_backup: the data volume is the only copy of the tracker"
            )
        if self.career_ops.public and not self.career_ops_enabled:
            raise ValueError(
                "career_ops.public requires enabled: career-ops only runs when it is enabled"
            )
        # pocket_id.public already requires an ingress, so no separate ingress check.
        if self.career_ops.public and not self.pocket_id.public:
            raise ValueError(
                "career_ops.public requires pocket_id.public: a visitor from the internet "
                "must reach the Pocket ID login"
            )
        if self.network_optimizer_enabled and not self.observability_enabled:
            raise ValueError(
                "network_optimizer requires observability: Network Optimizer writes its "
                "time series to the InfluxDB there"
            )
        if self.network_optimizer_oidc and not self.pocket_id_enabled:
            raise ValueError(
                "network_optimizer.oidc_client_id requires pocket_id: "
                "Pocket ID is the OIDC provider Network Optimizer signs in with"
            )
        if self.pegaprox_metrics and not self.observability_enabled:
            raise ValueError(
                "pegaprox.metrics requires observability: it is scraped by its Prometheus"
            )
        if self.matherlynet.playground and not self.nvidia_enabled:
            raise ValueError(
                "matherlynet.playground requires an NVIDIA node: LocalAI only "
                "runs when a node loads the nvidia kernel module"
            )
        if self.localai_webui_enabled:
            if not self.pocket_id_enabled:
                raise ValueError(
                    "localai.oidc_client_id requires pocket_id: Pocket ID is the WebUI's only sign-in"
                )
            if not self.nvidia_enabled:
                raise ValueError(
                    "localai.oidc_client_id requires an NVIDIA node: LocalAI only "
                    "runs when a node loads the nvidia kernel module"
                )

        cidrs = {
            "network.node_cidr": self.network.node_cidr,
            "kubernetes.pod_cidr": self.kubernetes.pod_cidr,
            "kubernetes.svc_cidr": self.kubernetes.svc_cidr,
        }
        names = list(cidrs)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                if cidrs[a].overlaps(cidrs[b]):
                    raise ValueError(f"{a} {cidrs[a]} overlaps {b} {cidrs[b]}")

        addresses = {
            "kubernetes.api.addr": self.kubernetes.api.addr,
            "gateways.internal": self.gateways.internal,
            "gateways.dns": self.gateways.dns,
            "network.default_gateway": self.network.default_gateway,
        } | {f"nodes[{i}].address": n.address for i, n in enumerate(self.nodes)}
        if self.gateways.external is not None:
            addresses["gateways.external"] = self.gateways.external
        seen: dict[IPv4Address, str] = {}
        for owner, addr in addresses.items():
            if addr in seen:
                raise ValueError(f"address {addr} is used by both {seen[addr]} and {owner}")
            seen[addr] = owner

        node_cidr = self.network.node_cidr
        for i, node in enumerate(self.nodes):
            if node.address not in node_cidr:
                raise ValueError(
                    f"nodes[{i}].address {node.address} is not inside node_cidr {node_cidr}"
                )
        if self.kubernetes.api.addr not in node_cidr:
            raise ValueError(
                f"kubernetes.api.addr {self.kubernetes.api.addr} is not inside node_cidr {node_cidr}"
            )
        # Without BGP the gateway VIPs are announced over L2 and must live in
        # the node network.
        if not self.cilium_bgp_enabled:
            for name in ("internal", "dns", "external"):
                addr = getattr(self.gateways, name)
                if addr is not None and addr not in node_cidr:
                    raise ValueError(
                        f"gateways.{name} {addr} is not inside node_cidr {node_cidr} "
                        "(required unless BGP is enabled)"
                    )

        for field, label in (("name", "name"), ("mac_addr", "MAC address")):
            values: dict[str, int] = {}
            for i, node in enumerate(self.nodes):
                value = getattr(node, field)
                if value in values:
                    raise ValueError(
                        f"duplicate node {label} {value!r} on nodes[{values[value]}] and nodes[{i}]"
                    )
                values[value] = i
        # Every cluster reads its domain and its tokens from the vault. Clearing it would also stop
        # the external-secrets apps from rendering, which deletes every Secret an ExternalSecret
        # owns. Last, so a config with another mistake reports that one first.
        if not self.onepassword_enabled:
            raise ValueError(
                "onepassword.vault is required: the domain and every secret are read from it"
            )
        return self


def format_errors(error: ValidationError) -> str:
    lines = []
    for err in error.errors():
        loc = ".".join(str(part) for part in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        lines.append(f"{loc}: {msg}" if loc else msg)
    return "\n".join(lines)


class ConfigError(Exception):
    pass


# Validate config_file and return the defaulted config as a plain dict.
# Raises ConfigError with a human-readable message.
def load(config_file: str = "cluster.toml") -> dict[str, Any]:
    path = Path(config_file)
    try:
        raw = tomllib.loads(path.read_text())
    except FileNotFoundError:
        raise ConfigError(f"{path}: file not found") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: invalid TOML: {e}") from None

    try:
        config = Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(format_errors(e)) from None

    # Unset optionals stay in the dump as None rather than being dropped:
    # makejinja renders with StrictUndefined, so a template testing
    # network.vlan_tag needs the key to exist.
    return config.model_dump(mode="json")


# JSON Schema for editor completion and validation of cluster.toml (taplo's
# #:schema directive). Cross-field rules and data-aware defaults only exist in
# the model validators, so the schema is an editing aid, not the gate.
def schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **Config.model_json_schema(),
    }


def main() -> int:
    if sys.argv[1:] == ["--schema"]:
        json.dump(schema(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    try:
        data = load(sys.argv[1] if len(sys.argv) > 1 else "cluster.toml")
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    json.dump(data, sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
