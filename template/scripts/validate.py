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
from urllib.parse import unquote, urlsplit

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
# A secret rendered inside a double-quoted YAML string, where a quote or a
# backslash would change the value. Flux substitutes ${...} in the rendered
# manifest, so a dollar sign is out too.
type Secret = Annotated[str, Field(pattern=r'^[^"\\\s$]*$')]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Reject a section where only some of the fields in names are set.
def _all_or_none(model: Model, label: str, names: tuple[str, ...]) -> None:
    unset = [name for name in names if getattr(model, name) == ""]
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


class Domain(Model):
    name: Fqdn


class Dns(Model):
    provider: Literal["cloudflare", "none"] = "cloudflare"
    token: str = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.provider == "cloudflare" and not self.token:
            raise ValueError("token is required when dns.provider is 'cloudflare'")
        if self.provider == "none" and self.token:
            raise ValueError("token must be empty when dns.provider is 'none'")
        return self


class Ingress(Model):
    mode: Literal["cloudflare-tunnel", "direct", "none"] = "cloudflare-tunnel"


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
    oidc_client_secret: Secret = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "cilium.hubble", ("oidc_client_id", "oidc_client_secret"))
        return self


class Cilium(Model):
    loadbalancer_mode: Literal["dsr", "snat"] = "dsr"
    bgp: Bgp = Bgp()
    hubble: Hubble = Hubble()


class PostgresBackup(Model):
    # S3 API endpoint of the object store, without a path.
    endpoint: str = Field(default="", pattern=r"^(https://[^/\s]+)?$")
    bucket: str = Field(default="", pattern=r"^([a-z0-9][a-z0-9.-]*[a-z0-9])?$")
    access_key_id: Secret = ""
    secret_access_key: Secret = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "backup", ("endpoint", "bucket", "access_key_id", "secret_access_key"))
        return self


class Postgres(Model):
    backup: PostgresBackup = PostgresBackup()


class Redis(Model):
    # Shared by every Redis the redis component creates. Clients put it in a
    # connection URL unencoded, hence letters and digits only.
    password: str = Field(default="", pattern=r"^([A-Za-z0-9]{24,})?$")


class Observability(Model):
    grafana_password: Secret = ""
    # InfluxDB rejects a password shorter than 8 characters.
    influxdb_password: Secret = Field(default="", pattern=r'^([^"\\\s$]{8,})?$')
    influxdb_token: Secret = ""
    # Where Alertmanager sends alerts. Unset, every alert goes to the null receiver.
    discord_webhook: str = Field(
        default="", pattern=r"^(https://discord(app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+)?$"
    )
    # The OIDC client created for Grafana in the Pocket ID admin UI.
    grafana_oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    grafana_oidc_client_secret: Secret = ""
    # Encrypts Grafana's stored data source secrets, all provisioned here and re-encoded
    # at start. The advisor flags the built-in default. Never change it without reprovisioning.
    grafana_secret_key: Secret = Field(default="", pattern=r'^([^"\\\s$]{32,})?$')
    # A GitHub App for Grafana's GitHub data source. The private key is the PEM file
    # GitHub downloads, kept to base64 lines so Grafana's $VAR expansion leaves it alone.
    github_app_id: str = Field(default="", pattern=r"^[0-9]*$")
    github_app_installation_id: str = Field(default="", pattern=r"^[0-9]*$")
    github_app_private_key: str = Field(
        default="",
        pattern=r"^(-----BEGIN [A-Z ]+-----\n[A-Za-z0-9+/=\n]+-----END [A-Z ]+-----\n?)?$",
    )
    # An internal integration token for Grafana's Sentry data source.
    sentry_org: str = Field(default="", pattern=r"^[a-z0-9-]*$")
    sentry_token: Secret = ""
    # Regional organizations use their region's host.
    sentry_url: str = Field(default="https://sentry.io", pattern=r"^https://[^/\s]+$")

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(
            self, "observability", ("grafana_password", "influxdb_password", "influxdb_token")
        )
        if self.discord_webhook and not self.grafana_password:
            raise ValueError(
                "discord_webhook requires grafana_password, influxdb_password and "
                "influxdb_token: Alertmanager only runs with the rest of the stack"
            )
        _all_or_none(
            self, "observability", ("grafana_oidc_client_id", "grafana_oidc_client_secret")
        )
        if self.grafana_oidc_client_id and not self.grafana_password:
            raise ValueError(
                "grafana_oidc_client_id requires grafana_password, influxdb_password and "
                "influxdb_token: Grafana only runs with the rest of the stack"
            )
        if self.grafana_secret_key and not self.grafana_password:
            raise ValueError(
                "grafana_secret_key requires grafana_password, influxdb_password and "
                "influxdb_token: Grafana only runs with the rest of the stack"
            )
        _all_or_none(
            self,
            "observability",
            ("github_app_id", "github_app_installation_id", "github_app_private_key"),
        )
        _all_or_none(self, "observability", ("sentry_org", "sentry_token"))
        for name in ("github_app_id", "sentry_org"):
            if getattr(self, name) and not self.grafana_password:
                raise ValueError(
                    f"{name} requires grafana_password, influxdb_password and "
                    "influxdb_token: Grafana only runs with the rest of the stack"
                )
        return self


class Unifi(Model):
    # Address of the UniFi console, without a path.
    host: str = Field(default="", pattern=r"^(https://[^/\s]+)?$")
    api_key: Secret = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "unifi", ("host", "api_key"))
        return self


class PocketId(Model):
    # Encrypts the token signing keys in Pocket ID's database. Pocket ID rejects
    # a key under 16 bytes. The characters are the ones Secret allows.
    encryption_key: str = Field(default="", pattern=r'^([^"\\\s$]{16,})?$')
    # Also attaches the route to the external gateway, so the internet reaches it.
    public: bool = False


class Radar(Model):
    # The OIDC client created for Radar in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    oidc_client_secret: Secret = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "radar", ("oidc_client_id", "oidc_client_secret"))
        return self


class Matherlynet(Model):
    # Signs the site's sessions.
    better_auth_secret: Secret = ""
    admin_email: str = Field(default="", pattern=r'^([^@\s"\\$]+@[^@\s"\\$]+\.[^@\s"\\$]+)?$')
    # Where the site sends mail. Unset, it sends none. A bare host name makes the
    # site's mail library throw on every request, so require the URL form.
    smtp_url: str = Field(default="", pattern=r'^(smtps?://[^"\\\s$]+)?$')
    # Sender address, which may carry a display name: "Name <a@b.c>".
    mail_from: str = Field(default="", pattern=r'^[^"\\$\r\n]*$')
    # OAuth apps for signing in with GitHub or Google.
    github_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    github_client_secret: Secret = ""
    google_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    google_client_secret: Secret = ""
    # Lets the site call the in-cluster llama-server.
    playground: bool = False

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "matherlynet", ("better_auth_secret", "admin_email"))
        _all_or_none(self, "matherlynet", ("github_client_id", "github_client_secret"))
        _all_or_none(self, "matherlynet", ("google_client_id", "google_client_secret"))
        if not self.better_auth_secret:
            for name in (
                "smtp_url",
                "mail_from",
                "github_client_id",
                "google_client_id",
                "playground",
            ):
                if getattr(self, name):
                    raise ValueError(
                        f"{name} requires better_auth_secret and admin_email: "
                        "the site only runs when both are set"
                    )
        return self


class ReactiveResume(Model):
    # Signs sessions and encrypts two-factor secrets; changing it signs everyone out.
    auth_secret: Secret = ""
    # Encrypts users' saved AI keys. The server refuses to start on fewer than 32 characters.
    encryption_secret: str = Field(default="", pattern=r'^([^"\\\s$]{32,})?$')
    # The OIDC client created for Reactive Resume in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    oidc_client_secret: Secret = ""
    # S3 API endpoint of the bucket that holds uploads, without a path.
    s3_endpoint: str = Field(default="", pattern=r"^(https://[^/\s]+)?$")
    s3_bucket: str = Field(default="", pattern=r"^([a-z0-9][a-z0-9.-]*[a-z0-9])?$")
    s3_access_key_id: Secret = ""
    s3_secret_access_key: Secret = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(
            self,
            "reactive_resume",
            (
                "auth_secret",
                "encryption_secret",
                "oidc_client_id",
                "oidc_client_secret",
                "s3_endpoint",
                "s3_bucket",
                "s3_access_key_id",
                "s3_secret_access_key",
            ),
        )
        return self


class Kener(Model):
    # Signs sessions and API keys. Kener's documentation asks for 32 characters.
    secret_key: str = Field(default="", pattern=r'^([^"\\\s$]{32,})?$')
    # Where Kener sends mail. smtps:// means TLS from the first byte. Kener
    # ignores its mail settings unless it has a host, a user and a password.
    smtp_url: str = Field(default="", pattern=r'^(smtps?://[^"\\\s$]+)?$')
    # Sender address of that mail.
    mail_from: str = Field(default="", pattern=r'^[^"\\$\r\n]*$')

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "kener", ("smtp_url", "mail_from"))
        if self.smtp_url and not self.secret_key:
            raise ValueError("smtp_url requires secret_key: Kener only runs when the key is set")
        if self.smtp_url:
            url = urlsplit(self.smtp_url)
            if not (url.hostname and url.username and url.password):
                raise ValueError("smtp_url needs a user, a password and a host")
            try:
                _ = url.port
            except ValueError:
                raise ValueError("smtp_url has a port that is not a number") from None
            # The decoded values go into a quoted YAML string that Flux substitutes.
            for part in (unquote(url.username), unquote(url.password)):
                if re.search(r'["\\\s$]', part):
                    raise ValueError(
                        "smtp_url user and password must not contain a double quote, "
                        "a backslash, a space or a dollar sign, even when encoded"
                    )
        return self


class NetworkOptimizer(Model):
    # Password of the app's built-in admin account. Its identity store refuses
    # a password without a digit.
    app_password: str = Field(default="", pattern=r'^([^"\\\s$]{8,})?$')
    # The OIDC client created for Network Optimizer in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    oidc_client_secret: Secret = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(self, "network_optimizer", ("oidc_client_id", "oidc_client_secret"))
        if self.app_password and not re.search(r"[0-9]", self.app_password):
            raise ValueError("app_password must contain a digit: the app refuses it otherwise")
        if self.oidc_client_id and not self.app_password:
            raise ValueError(
                "oidc_client_id requires app_password: Network Optimizer only runs "
                "when the password is set"
            )
        return self


class PegaProx(Model):
    # Master key that encrypts PegaProx's SQLite database and the Proxmox
    # credentials stored in it: 32 bytes as urlsafe base64 or as 64 hex characters.
    # Never change it once set: the database becomes unreadable.
    db_key: str = Field(default="", pattern=r"^([A-Za-z0-9_-]{43}=|[0-9a-fA-F]{64})?$")
    # The API token Prometheus scrapes /api/metrics with.
    metrics_token: Secret = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        if self.metrics_token and not self.db_key:
            raise ValueError(
                "metrics_token requires db_key: PegaProx only runs when the key is set"
            )
        return self


class Sure(Model):
    # Signs sessions, and Sure derives its database encryption keys from it.
    # Never change it once set: the encrypted columns become unreadable.
    secret_key_base: str = Field(default="", pattern=r'^([^"\\\s$]{64,})?$')
    # The OIDC client created for Sure in the Pocket ID admin UI.
    oidc_client_id: str = Field(default="", pattern=r"^[A-Za-z0-9._~-]*$")
    oidc_client_secret: Secret = ""
    # The Cloudflare account that owns the R2 bucket holding uploads.
    r2_account_id: str = Field(default="", pattern=r"^([0-9a-f]{32})?$")
    r2_bucket: str = Field(default="", pattern=r"^([a-z0-9][a-z0-9.-]*[a-z0-9])?$")
    r2_access_key_id: Secret = ""
    r2_secret_access_key: Secret = ""

    @model_validator(mode="after")
    def check(self) -> Self:
        _all_or_none(
            self,
            "sure",
            (
                "secret_key_base",
                "oidc_client_id",
                "oidc_client_secret",
                "r2_account_id",
                "r2_bucket",
                "r2_access_key_id",
                "r2_secret_access_key",
            ),
        )
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


class Config(Model):
    model_config = ConfigDict(extra="forbid", title="cluster.toml")

    network: Network
    kubernetes: Kubernetes
    gateways: Gateways
    repository: Repository
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
    sure: Sure = Sure()
    nodes: list[Node]

    @computed_field
    @property
    def cilium_bgp_enabled(self) -> bool:
        bgp = self.cilium.bgp
        return bgp.router_addr != "" and bgp.router_asn != "" and bgp.node_asn != ""

    # The UI has no login of its own, so Hubble is only turned on when its gateway login exists.
    @computed_field
    @property
    def hubble_enabled(self) -> bool:
        return self.cilium.hubble.oidc_client_id != ""

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

    # The backup fields are set all together or not at all.
    @computed_field
    @property
    def postgres_backup_enabled(self) -> bool:
        return self.postgres.backup.endpoint != ""

    # Gates components/redis, which gives an app that includes it a Redis of its own.
    @computed_field
    @property
    def redis_enabled(self) -> bool:
        return self.redis.password != ""

    # Gates the observability namespace, whose apps need all three secrets.
    @computed_field
    @property
    def observability_enabled(self) -> bool:
        return self.observability.grafana_password != ""

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
        return self.pocket_id.encryption_key != ""

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
        return self.matherlynet.better_auth_secret != ""

    # Gates Reactive Resume and its database. The fields are set all together or not at all.
    @computed_field
    @property
    def reactive_resume_enabled(self) -> bool:
        return self.reactive_resume.auth_secret != ""

    # Gates Kener and its database.
    @computed_field
    @property
    def kener_enabled(self) -> bool:
        return self.kener.secret_key != ""

    # kener.smtp_url as the separate settings Kener reads. Empty when it is unset.
    @computed_field
    @property
    def kener_smtp(self) -> dict[str, str]:
        if not self.kener.smtp_url:
            return {}
        url = urlsplit(self.kener.smtp_url)
        secure = url.scheme == "smtps"
        return {
            "host": url.hostname or "",
            "port": str(url.port or (465 if secure else 587)),
            "user": unquote(url.username or ""),
            "password": unquote(url.password or ""),
            "secure": "1" if secure else "0",
        }

    # Gates Network Optimizer.
    @computed_field
    @property
    def network_optimizer_enabled(self) -> bool:
        return self.network_optimizer.app_password != ""

    # Adds the Pocket ID sign-in to Network Optimizer.
    @computed_field
    @property
    def network_optimizer_oidc(self) -> bool:
        return self.network_optimizer.oidc_client_id != ""

    # Gates PegaProx.
    @computed_field
    @property
    def pegaprox_enabled(self) -> bool:
        return self.pegaprox.db_key != ""

    # Adds the Prometheus scrape and the Grafana dashboard for PegaProx.
    @computed_field
    @property
    def pegaprox_metrics(self) -> bool:
        return self.pegaprox.metrics_token != ""

    # Gates Sure and its database. The fields are set all together or not at all.
    @computed_field
    @property
    def sure_enabled(self) -> bool:
        return self.sure.secret_key_base != ""

    @computed_field
    @property
    def cluster_issuer(self) -> str:
        if self.dns.provider == "cloudflare":
            return "letsencrypt-production"
        return "internal-ca"

    # Single source for the machine and apiServer certificate SAN lists,
    # which live in separate patch files.
    @computed_field
    @property
    def cert_sans(self) -> list[str]:
        return ["127.0.0.1", str(self.kubernetes.api.addr), *(self.kubernetes.api.tls_sans or [])]

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
        if self.pocket_id_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "pocket_id requires postgres.backup: its database holds passkeys and "
                "signing keys, which cannot be recreated"
            )
        if self.pocket_id.public and not self.pocket_id_enabled:
            raise ValueError(
                "pocket_id.public requires pocket_id.encryption_key: Pocket ID only runs "
                "when the key is set"
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
            raise ValueError("kener requires redis.password: Kener's job queue lives in Redis")
        if self.kener_enabled and self.ingress.mode == "none":
            raise ValueError(
                "kener requires ingress.mode other than 'none': the status page is served "
                "on the external gateway"
            )
        if self.sure_enabled and not self.postgres_backup_enabled:
            raise ValueError(
                "sure requires postgres.backup: its database holds accounts and "
                "financial history, which cannot be recreated"
            )
        if self.sure_enabled and not self.redis_enabled:
            raise ValueError("sure requires redis.password: Sidekiq's queue lives in Redis")
        if self.sure_enabled and not self.pocket_id_enabled:
            raise ValueError("sure requires pocket_id: Pocket ID is Sure's login")
        # pocket_id.public already requires an ingress, so no separate ingress check.
        if self.sure_enabled and not self.pocket_id.public:
            raise ValueError(
                "sure requires pocket_id.public: Sure is served only on the external "
                "gateway, and a visitor from the internet must reach the Pocket ID login"
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
                "pegaprox.metrics_token requires observability: it is scraped by its Prometheus"
            )
        if self.matherlynet.playground and not self.nvidia_enabled:
            raise ValueError(
                "matherlynet.playground requires an NVIDIA node: llama-server only "
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
