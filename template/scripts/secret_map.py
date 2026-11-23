"""Where each secret that leaves cluster.toml lives in 1Password.

One vault item per cluster.toml section, titled with the section name in hyphens.
A field's label is the name the field had in cluster.toml, in upper case.
secrets_check.py checks the vault against this map.
"""

from collections.abc import Callable
from typing import Any, NamedTuple


class Entry(NamedTuple):
    item: str
    field: str
    # Where the value lived before it moved: a former cluster.toml path,
    # `<path>#<part>` for one part of a split value, `file:<name>#<key>` for a
    # value from a file, or `copy:<path>` for a value that also stays in cluster.toml.
    source: str
    # A key of GATES, or a config path that is truthy when the field is needed.
    requires: str
    # What the removed validate.py type checked, for a value that is set.
    pattern: str | None


# The label that stands for every name in the list at `<source>_keys`.
EACH_KEY = "*"

_SAFE = r'[^\s"\\$,@]+'
_EMAIL = rf"{_SAFE}@{_SAFE}\.{_SAFE}"
_RULE = rf"({_EMAIL}|@{_SAFE}\.{_SAFE})"
SECRET = r'^[^"\\\s$]*$'
LONG_SECRET = r'^([^"\\\s$]{32,})?$'
API_KEY = r"^([A-Za-z0-9]{32,})?$"
S3_ACCESS_KEY = r"^([A-Za-z0-9]{16,})?$"
URL_CREDENTIAL = r"^[A-Za-z0-9_-]*$"
# A VAPID key from `web-push generate-vapid-keys`, unpadded base64url.
BASE64URL = r"^[A-Za-z0-9_-]{40,}$"
BUCKET = r"^([a-z0-9][a-z0-9.-]*[a-z0-9])?$"
ALNUM_24 = r"^([A-Za-z0-9]{24,})?$"
MAIL_FROM = r'^[^"\\$\r\n]*$'
EMAIL_ADDRESS = rf"^({_EMAIL})?$"
EMAIL_LIST = rf"^({_EMAIL})(,({_EMAIL}))*$"
EMAIL_RULE_LIST = rf"^({_RULE})(,({_RULE}))*$"
# Network Optimizer's identity store refuses a password without a digit.
DIGIT_PASSWORD = r'^(?=[^"\\\s$]*[0-9])[^"\\\s$]{8,}$'

# (cluster.toml path, requires, pattern), one row per field that maps to one label.
# fmt: off
_FIELDS: list[tuple[str, str, str | None]] = [
    ("dns.token", "dns_cloudflare", None),
    ("cilium.hubble.oidc_client_secret", "hubble_enabled", SECRET),
    ("postgres.backup.access_key_id", "postgres_backup_enabled", SECRET),
    ("postgres.backup.secret_access_key", "postgres_backup_enabled", SECRET),
    ("etcd_backup.bucket", "etcd_backup_enabled", BUCKET),
    ("etcd_backup.access_key", "etcd_backup_enabled", URL_CREDENTIAL),
    ("etcd_backup.secret_key", "etcd_backup_enabled", URL_CREDENTIAL),
    ("volume_backup.bucket", "volume_backup_enabled", BUCKET),
    ("volume_backup.access_key", "volume_backup_enabled", URL_CREDENTIAL),
    ("volume_backup.secret_key", "volume_backup_enabled", URL_CREDENTIAL),
    ("redis.password", "redis_enabled", ALNUM_24),
    ("observability.grafana_password", "observability_enabled", SECRET),
    ("observability.influxdb_password", "observability_enabled", r'^([^"\\\s$]{8,})?$'),
    ("observability.influxdb_token", "observability_enabled", SECRET),
    ("observability.discord_webhook", "observability.discord", r'^(https://discord(app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+)?$'),
    ("observability.heartbeat_url", "observability.heartbeat", r'^(https://[^\s"\\]+)?$'),
    ("observability.grafana_oidc_client_secret", "observability.grafana_oidc_client_id", SECRET),
    ("observability.grafana_secret_key", "observability.secret_key", LONG_SECRET),
    ("observability.github_app_private_key", "observability.github_app_id", r'^(-----BEGIN [A-Z ]+-----\n[A-Za-z0-9+/=\n]+-----END [A-Z ]+-----\n?)?$'),
    ("observability.sentry_token", "observability.sentry_org", SECRET),
    ("unifi.api_key", "unifi_dns_enabled", SECRET),
    ("pocket_id.encryption_key", "pocket_id_enabled", r'^([^"\\\s$]{16,})?$'),
    ("radar.oidc_client_secret", "radar_enabled", SECRET),
    ("matherlynet.better_auth_secret", "matherlynet_enabled", SECRET),
    ("matherlynet.admin_email", "matherlynet_enabled", EMAIL_ADDRESS),
    ("matherlynet.smtp_url", "matherlynet.smtp", r'^(smtps?://[^"\\\s$]+)?$'),
    ("matherlynet.mail_from", "matherlynet.mail", MAIL_FROM),
    ("matherlynet.github_client_secret", "matherlynet.github", SECRET),
    ("matherlynet.google_client_secret", "matherlynet.google", SECRET),
    ("reactive_resume.auth_secret", "reactive_resume_enabled", LONG_SECRET),
    ("reactive_resume.encryption_secret", "reactive_resume_enabled", LONG_SECRET),
    ("reactive_resume.oidc_client_secret", "reactive_resume_enabled", SECRET),
    ("reactive_resume.s3_endpoint", "reactive_resume_enabled", r'^(https://[^/\s]+)?$'),
    ("reactive_resume.s3_access_key_id", "reactive_resume_enabled", SECRET),
    ("reactive_resume.s3_secret_access_key", "reactive_resume_enabled", SECRET),
    ("kener.secret_key", "kener_enabled", LONG_SECRET),
    ("kener.mail_from", "kener_smtp", MAIL_FROM),
    ("network_optimizer.app_password", "network_optimizer_enabled", DIGIT_PASSWORD),
    ("network_optimizer.oidc_client_secret", "network_optimizer_oidc", SECRET),
    ("pegaprox.db_key", "pegaprox_enabled", r'^([A-Za-z0-9_-]{43}=|[0-9a-fA-F]{64})?$'),
    ("pegaprox.metrics_token", "pegaprox_metrics", SECRET),
    ("actual_budget.oidc_client_secret", "actual_budget_enabled", SECRET),
    ("media.sonarr_api_key", "media_enabled", API_KEY),
    ("media.radarr_api_key", "media_enabled", API_KEY),
    ("media.prowlarr_api_key", "media_enabled", API_KEY),
    ("media.sabnzbd_api_key", "media_enabled", API_KEY),
    ("media.sabnzbd_nzb_key", "media_enabled", API_KEY),
    ("media.oidc_client_secret", "media_enabled", SECRET),
    ("media.plex_token", "media_plex_enabled", SECRET),
    ("ai_workspace.oidc_client_secret", "ai_workspace_enabled", SECRET),
    ("ai_workspace.auth_secret", "ai_workspace_enabled", LONG_SECRET),
    ("ai_workspace.allowed_emails", "ai_workspace.allowlist", EMAIL_RULE_LIST),
    ("ai_workspace.admin_emails", "ai_workspace.admins", EMAIL_LIST),
    ("ai_workspace.browsing_token", "ai_workspace.browsing", API_KEY),
    ("ai_kb.jwt_secret", "ai_kb_enabled", LONG_SECRET),
    ("ai_kb.aes_key", "ai_kb_enabled", r'^([A-Za-z0-9]{32})?$'),
    ("ai_kb.oidc_client_secret", "ai_kb_oidc", SECRET),
    ("ai_kb.rustfs_access_key", "ai_kb_rustfs", S3_ACCESS_KEY),
    ("ai_kb.rustfs_secret_key", "ai_kb_rustfs", API_KEY),
    ("ai_kb.neo4j_password", "ai_kb_neo4j", API_KEY),
    ("ai_kb.searxng_secret", "ai_kb_searxng", API_KEY),
    ("rustfs.access_key", "rustfs_enabled", S3_ACCESS_KEY),
    ("rustfs.secret_key", "rustfs_enabled", API_KEY),
    ("langfuse.public_key", "langfuse_enabled", r'^(pk-lf-[A-Za-z0-9-]{32,})?$'),
    ("langfuse.secret_key", "langfuse_enabled", r'^(sk-lf-[A-Za-z0-9-]{32,})?$'),
    ("langfuse.salt", "langfuse_enabled", API_KEY),
    ("langfuse.encryption_key", "langfuse_enabled", r'^([0-9a-fA-F]{64})?$'),
    ("langfuse.nextauth_secret", "langfuse_enabled", API_KEY),
    ("langfuse.oidc_client_secret", "langfuse_enabled", SECRET),
    ("langfuse.clickhouse_password", "langfuse_enabled", ALNUM_24),
    ("langfuse.rustfs_access_key", "langfuse_enabled", S3_ACCESS_KEY),
    ("langfuse.rustfs_secret_key", "langfuse_enabled", API_KEY),
    ("itsaplan.better_auth_secret", "itsaplan_enabled", LONG_SECRET),
    ("itsaplan.app_encryption_key", "itsaplan_enabled", LONG_SECRET),
    ("itsaplan.rustfs_access_key", "itsaplan_enabled", S3_ACCESS_KEY),
    ("itsaplan.rustfs_secret_key", "itsaplan_enabled", API_KEY),
    ("itsaplan.web_push_vapid_public_key", "itsaplan.web_push", BASE64URL),
    ("itsaplan.web_push_vapid_private_key", "itsaplan.web_push", BASE64URL),
    ("itsaplan.web_push_subject", "itsaplan.web_push", r"^(mailto:[^\s@]+@[^\s@]+|https://\S+)$"),
    ("cliproxyapi.management_key", "cliproxyapi_enabled", LONG_SECRET),
    ("cliproxyapi.api_key", "cliproxyapi_enabled", LONG_SECRET),
    ("cliproxyapi.manager_admin_key", "cliproxyapi_enabled", LONG_SECRET),
    ("cliproxyapi.ohmycpa_master_key", "ohmycpa_enabled", r'^$|^[0-9a-f]{64}$'),
    ("cliproxyapi.github_token", "cliproxyapi.github", None),
    ("career_ops.oidc_client_secret", "career_ops_enabled", SECRET),
    ("career_ops.publish_secret", "career_ops_enabled", LONG_SECRET),
    ("career_ops.publish_auth_secret", "career_ops_enabled", LONG_SECRET),
    ("career_ops.publish_oidc_client_secret", "career_ops_enabled", SECRET),
    ("career_ops.publish_allowed_emails", "career_ops_enabled", EMAIL_LIST),
    ("career_ops.claude_oauth_token", "career_ops_oauth", SECRET),
    ("career_ops.anthropic_auth_token", "career_ops_proxy", SECRET),
    ("career_ops.publish_api_key", "career_ops.publish", SECRET),
    ("firecrawl.postgres_password", "firecrawl_enabled", ALNUM_24),
    ("firecrawl.gateway_api_key", "firecrawl_enabled", API_KEY),
    ("localai.api_key", "nvidia_enabled", API_KEY),
    ("localai.oidc_client_secret", "localai_webui_enabled", SECRET),
    ("github_runner.token", "github_runner_enabled", SECRET),
]
# fmt: on


def _entry(path: str, requires: str, pattern: str | None) -> Entry:
    *section, name = path.split(".")
    return Entry("-".join(section).replace("_", "-"), name.upper(), path, requires, pattern)


_TUNNEL_FILE = "file:cloudflare-tunnel.json"

ENTRIES: list[Entry] = [
    *(_entry(*row) for row in _FIELDS),
    # kener.smtp_url is stored as the separate settings Kener reads.
    Entry("kener", "SMTP_HOST", "kener.smtp_url#host", "kener_smtp", r"^\S+$"),
    Entry("kener", "SMTP_PORT", "kener.smtp_url#port", "kener_smtp", r"^[0-9]+$"),
    Entry("kener", "SMTP_SECURE", "kener.smtp_url#secure", "kener_smtp", r"^[01]$"),
    Entry("kener", "SMTP_USER", "kener.smtp_url#user", "kener_smtp", SECRET),
    Entry("kener", "SMTP_PASS", "kener.smtp_url#password", "kener_smtp", SECRET),
    # One field per key of the open-ended env map.
    Entry("ai-workspace-env", EACH_KEY, "ai_workspace.env", "ai_workspace_enabled", SECRET),
    Entry("cloudflare-tunnel", "ACCOUNT_TAG", f"{_TUNNEL_FILE}#AccountTag", "tunnel", None),
    Entry("cloudflare-tunnel", "TUNNEL_SECRET", f"{_TUNNEL_FILE}#TunnelSecret", "tunnel", None),
    Entry("flux", "WEBHOOK_TOKEN", "file:flux-webhook-token.txt", "webhook", None),
    Entry("cluster", "SECRET_DOMAIN", "copy:domain.name", "always", None),
]

# Every former cluster.toml field that the model no longer has.
MOVING_PATHS: frozenset[str] = frozenset(
    e.source.partition("#")[0] for e in ENTRIES if ":" not in e.source
)


def lookup(config: dict[str, Any], dotted: str) -> Any:
    """The value at a dotted path, or None when any part is missing."""
    value: Any = config
    for key in dotted.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value


# The requirements that are not one truthy config path.
GATES: dict[str, Callable[[dict[str, Any]], bool]] = {
    "always": lambda c: True,
    "dns_cloudflare": lambda c: lookup(c, "dns.provider") == "cloudflare",
    "tunnel": lambda c: lookup(c, "ingress.mode") == "cloudflare-tunnel",
    "webhook": lambda c: lookup(c, "repository.webhook_provider") not in (None, "none"),
    # Exactly one Claude credential, the one career_ops.claude_credential names.
    "career_ops_proxy": lambda c: bool(
        c.get("career_ops_enabled") and lookup(c, "career_ops.claude_credential") == "proxy"
    ),
    "career_ops_oauth": lambda c: bool(
        c.get("career_ops_enabled") and lookup(c, "career_ops.claude_credential") != "proxy"
    ),
}


def required(entry: Entry, config: dict[str, Any]) -> bool:
    gate = GATES.get(entry.requires)
    return gate(config) if gate else bool(lookup(config, entry.requires))


def items() -> dict[str, list[Entry]]:
    grouped: dict[str, list[Entry]] = {}
    for entry in ENTRIES:
        grouped.setdefault(entry.item, []).append(entry)
    return grouped
