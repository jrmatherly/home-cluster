"""Unit tests for the cluster.toml validator.

Run from the repo root:
    uv run --locked pytest template/scripts/test_validate.py -q
"""

import json
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from pydantic import ValidationError
from validate import Config, ConfigError, format_errors, load, schema

REPO_ROOT = Path(__file__).parents[2]
VALID = sorted((REPO_ROOT / ".github/template-tests/valid").glob("*.toml"))
INVALID = sorted((REPO_ROOT / ".github/template-tests/invalid").glob("*.toml"))


def config_from(fixture: str, **overrides) -> dict:
    raw = tomllib.loads((REPO_ROOT / ".github/template-tests/valid" / fixture).read_text())
    for dotted, value in overrides.items():
        target = raw
        *parents, leaf = dotted.split(".")
        for key in parents:
            target = target.setdefault(key, {})
        if value is None:
            target.pop(leaf, None)
        else:
            target[leaf] = value
    return raw


@pytest.mark.parametrize("fixture", VALID, ids=lambda p: p.stem)
def test_valid_fixture_accepted(fixture: Path):
    load(str(fixture))


@pytest.mark.parametrize("fixture", INVALID, ids=lambda p: p.stem)
def test_invalid_fixture_rejected(fixture: Path):
    with pytest.raises(ConfigError):
        load(str(fixture))


def _load_raw(raw: dict) -> Config:
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(format_errors(e)) from None


def test_host_bits_error_suggests_network_address():
    raw = config_from("public.toml", **{"network.node_cidr": "10.10.10.5/24"})
    with pytest.raises(ConfigError, match=r"did you mean 10\.10\.10\.0/24"):
        _load_raw(raw)


def test_duplicate_address_names_both_owners():
    raw = config_from("public.toml")
    raw["nodes"][0]["address"] = raw["gateways"]["internal"]
    with pytest.raises(ConfigError, match=r"gateways\.internal and nodes\[0\]\.address"):
        _load_raw(raw)


def test_default_gateway_derived_from_node_cidr():
    raw = config_from("private.toml")
    assert "default_gateway" not in raw["network"]
    data = _load_raw(raw).model_dump(mode="json")
    assert data["network"]["default_gateway"] == "10.10.10.1"


def test_coredns_addr_default_and_override():
    raw = config_from("private.toml")
    assert _load_raw(raw).model_dump(mode="json")["kubernetes"]["coredns_addr"] == "10.43.0.10"
    raw = config_from("private.toml", **{"kubernetes.coredns_addr": "10.43.0.53"})
    assert _load_raw(raw).model_dump(mode="json")["kubernetes"]["coredns_addr"] == "10.43.0.53"
    raw = config_from("private.toml", **{"kubernetes.coredns_addr": "192.168.9.9"})
    with pytest.raises(ConfigError, match="not inside svc_cidr"):
        _load_raw(raw)


def test_spegel_enabled_follows_node_count():
    two_nodes = config_from("private.toml")
    assert _load_raw(two_nodes).spegel.enabled is True
    one_node = config_from("private.toml")
    one_node["nodes"] = one_node["nodes"][:1]
    assert _load_raw(one_node).spegel.enabled is False
    empty_section = config_from("private.toml", spegel={})
    assert _load_raw(empty_section).spegel.enabled is True
    explicit = config_from("private.toml", **{"spegel.enabled": False})
    assert _load_raw(explicit).spegel.enabled is False


def test_controller_count_ignores_workers():
    raw = config_from("private.toml")
    assert [n["controller"] for n in raw["nodes"]] == [True, False]
    assert _load_raw(raw).controller_count == 1
    raw["nodes"][1]["controller"] = True
    assert _load_raw(raw).controller_count == 2


def test_nvidia_enabled_follows_kernel_modules():
    raw = config_from("public.toml", **{"matherlynet.playground": False})
    assert raw["nodes"][1]["kernel_modules"] == ["nvidia", "nvidia_uvm"]
    assert _load_raw(raw).nvidia_enabled is True
    raw["nodes"][1]["kernel_modules"] = ["nvidia_uvm"]
    assert _load_raw(raw).nvidia_enabled is False
    assert _load_raw(config_from("single-node.toml")).nvidia_enabled is False


def test_derived_fields_are_not_settable():
    raw = config_from("public.toml", cilium_bgp_enabled=True)
    with pytest.raises(ConfigError, match="cilium_bgp_enabled"):
        _load_raw(raw)
    raw = config_from("public.toml", controller_count=3)
    with pytest.raises(ConfigError, match="controller_count"):
        _load_raw(raw)


def test_cert_sans_single_source():
    raw = config_from("public.toml")
    assert _load_raw(raw).cert_sans == ["127.0.0.1", "10.10.10.254", "example.com"]
    raw = config_from("private.toml")
    assert _load_raw(raw).cert_sans == ["127.0.0.1", "10.10.10.254"]


def test_ingress_mode_follows_dns_provider():
    cloudflare = config_from("public.toml", ingress=None)
    assert _load_raw(cloudflare).ingress.mode == "cloudflare-tunnel"
    internal = config_from("internal.toml")
    assert (REPO_ROOT / ".github/template-tests/valid/internal.toml").exists()
    assert "ingress" not in internal
    assert _load_raw(internal).ingress.mode == "none"


def test_direct_mode_requires_cloudflare_dns():
    raw = config_from("internal.toml", **{"ingress.mode": "direct"})
    with pytest.raises(ConfigError, match="requires dns.provider 'cloudflare'"):
        _load_raw(raw)


def test_schematic_id_inherits_from_talos_section():
    raw = config_from("public.toml")
    cfg = _load_raw(raw)
    assert cfg.nodes[0].schematic_id == cfg.talos.schematic_id
    assert cfg.nodes[1].schematic_id is not None


def test_partial_bgp_rejected():
    raw = config_from(
        "private.toml", **{"cilium.bgp.router_addr": "10.10.1.1", "cilium.bgp.router_asn": "64513"}
    )
    with pytest.raises(ConfigError, match="partially configured"):
        _load_raw(raw)


POSTGRES_BACKUP = {
    "postgres.backup.endpoint": "https://fake.r2.cloudflarestorage.com",
    "postgres.backup.bucket": "fake",
    "postgres.backup.access_key_id": "fake",
    "postgres.backup.secret_access_key": "fake",
}


def test_postgres_backup_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).postgres_backup_enabled is False
    assert _load_raw(config_from("private.toml", **POSTGRES_BACKUP)).postgres_backup_enabled is True


def test_partial_postgres_backup_names_missing_fields():
    raw = config_from("private.toml", **POSTGRES_BACKUP | {"postgres.backup.bucket": None})
    with pytest.raises(ConfigError, match=r"partially configured.*\(missing: bucket\)"):
        _load_raw(raw)


def test_postgres_backup_endpoint_must_be_https_host():
    raw = config_from(
        "private.toml",
        **POSTGRES_BACKUP | {"postgres.backup.endpoint": "https://fake.example.com/bucket"},
    )
    with pytest.raises(ConfigError, match=r"postgres\.backup\.endpoint"):
        _load_raw(raw)


def test_postgres_backup_key_rejects_yaml_escapes():
    raw = config_from(
        "private.toml", **POSTGRES_BACKUP | {"postgres.backup.secret_access_key": "a\\tb"}
    )
    with pytest.raises(ConfigError, match=r"postgres\.backup\.secret_access_key"):
        _load_raw(raw)


OBSERVABILITY = {
    "observability.grafana_password": "fake",
    "observability.influxdb_password": "fakefake",
    "observability.influxdb_token": "fake",
}


def test_observability_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).observability_enabled is False
    assert _load_raw(config_from("private.toml", **OBSERVABILITY)).observability_enabled is True


def test_partial_observability_names_missing_fields():
    raw = config_from("private.toml", **OBSERVABILITY | {"observability.influxdb_token": None})
    with pytest.raises(ConfigError, match=r"partially configured.*\(missing: influxdb_token\)"):
        _load_raw(raw)


def test_influxdb_password_needs_eight_characters():
    raw = config_from(
        "private.toml", **OBSERVABILITY | {"observability.influxdb_password": "short"}
    )
    with pytest.raises(ConfigError, match=r"observability\.influxdb_password"):
        _load_raw(raw)


DISCORD_WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/example-token"


def test_discord_webhook_accepted_with_observability():
    raw = config_from(
        "private.toml", **OBSERVABILITY | {"observability.discord_webhook": DISCORD_WEBHOOK}
    )
    assert _load_raw(raw).observability.discord_webhook == DISCORD_WEBHOOK


def test_discord_webhook_requires_observability():
    raw = config_from("private.toml", **{"observability.discord_webhook": DISCORD_WEBHOOK})
    with pytest.raises(ConfigError, match=r"discord_webhook requires grafana_password"):
        _load_raw(raw)


def test_discord_webhook_must_be_discord_url():
    raw = config_from(
        "private.toml",
        **OBSERVABILITY | {"observability.discord_webhook": "https://example.com/hook/1/abc"},
    )
    with pytest.raises(ConfigError, match=r"observability\.discord_webhook"):
        _load_raw(raw)


UNIFI = {"unifi.host": "https://192.0.2.1", "unifi.api_key": "fake"}


def test_unifi_dns_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).unifi_dns_enabled is False
    assert _load_raw(config_from("private.toml", **UNIFI)).unifi_dns_enabled is True


def test_unifi_dns_addr_is_the_console_address_only_when_it_is_an_ip():
    assert _load_raw(config_from("private.toml")).unifi_dns_addr == ""
    assert _load_raw(config_from("private.toml", **UNIFI)).unifi_dns_addr == "192.0.2.1"
    with_port = UNIFI | {"unifi.host": "https://192.0.2.1:8443"}
    assert _load_raw(config_from("private.toml", **with_port)).unifi_dns_addr == "192.0.2.1"
    by_name = UNIFI | {"unifi.host": "https://unifi.example.com"}
    assert _load_raw(config_from("private.toml", **by_name)).unifi_dns_addr == ""


def test_partial_unifi_names_missing_field():
    raw = config_from("private.toml", **UNIFI | {"unifi.api_key": None})
    with pytest.raises(ConfigError, match=r"partially configured.*\(missing: api_key\)"):
        _load_raw(raw)


POCKET_ID = POSTGRES_BACKUP | {"pocket_id.encryption_key": "fakefakefakefake"}
RADAR = POCKET_ID | {"radar.oidc_client_id": "fake", "radar.oidc_client_secret": "fake"}


def test_pocket_id_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).pocket_id_enabled is False
    assert _load_raw(config_from("private.toml", **POCKET_ID)).pocket_id_enabled is True


def test_pocket_id_key_needs_sixteen_characters():
    raw = config_from("private.toml", **POCKET_ID | {"pocket_id.encryption_key": "fifteen-chars-x"})
    with pytest.raises(ConfigError, match=r"pocket_id\.encryption_key"):
        _load_raw(raw)


def test_pocket_id_requires_postgres_backup():
    raw = config_from("private.toml", **{"pocket_id.encryption_key": "fakefakefakefake"})
    with pytest.raises(ConfigError, match=r"pocket_id requires postgres\.backup"):
        _load_raw(raw)


def test_pocket_id_public_accepted_with_pocket_id():
    raw = config_from("private.toml", **POCKET_ID | {"pocket_id.public": True})
    assert _load_raw(raw).pocket_id.public is True


def test_pocket_id_public_requires_pocket_id():
    raw = config_from("private.toml", **{"pocket_id.public": True})
    with pytest.raises(ConfigError, match=r"pocket_id\.public requires pocket_id\.encryption_key"):
        _load_raw(raw)


def test_pocket_id_public_requires_ingress():
    raw = config_from(
        "private.toml", **POCKET_ID | {"pocket_id.public": True, "ingress.mode": "none"}
    )
    with pytest.raises(ConfigError, match=r"pocket_id\.public requires ingress\.mode"):
        _load_raw(raw)


def test_radar_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POCKET_ID)).radar_enabled is False
    assert _load_raw(config_from("private.toml", **RADAR)).radar_enabled is True


def test_partial_radar_names_missing_field():
    raw = config_from("private.toml", **RADAR | {"radar.oidc_client_secret": None})
    with pytest.raises(ConfigError, match=r"partially configured.*\(missing: oidc_client_secret\)"):
        _load_raw(raw)


def test_radar_requires_pocket_id():
    raw = config_from("private.toml", **RADAR | {"pocket_id.encryption_key": None})
    with pytest.raises(ConfigError, match=r"radar requires pocket_id"):
        _load_raw(raw)


HUBBLE = POCKET_ID | {
    "cilium.hubble.oidc_client_id": "hubble",
    "cilium.hubble.oidc_client_secret": "fake",
}


def test_hubble_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POCKET_ID)).hubble_enabled is False
    assert _load_raw(config_from("private.toml", **HUBBLE)).hubble_enabled is True


def test_partial_hubble_names_missing_field():
    raw = config_from("private.toml", **HUBBLE | {"cilium.hubble.oidc_client_id": None})
    with pytest.raises(
        ConfigError, match=r"cilium\.hubble is partially configured.*\(missing: oidc_client_id\)"
    ):
        _load_raw(raw)


def test_hubble_requires_pocket_id():
    raw = config_from("private.toml", **HUBBLE | {"pocket_id.encryption_key": None})
    with pytest.raises(ConfigError, match=r"cilium\.hubble requires pocket_id"):
        _load_raw(raw)


GRAFANA_OIDC = {
    "observability.grafana_oidc_client_id": "grafana",
    "observability.grafana_oidc_client_secret": "fake",
}


def test_grafana_oidc_accepted_with_observability_and_pocket_id():
    raw = config_from("private.toml", **POCKET_ID | OBSERVABILITY | GRAFANA_OIDC)
    observability = _load_raw(raw).observability
    assert observability.grafana_oidc_client_id == "grafana"
    assert observability.grafana_oidc_client_secret == "fake"


def test_partial_grafana_oidc_names_missing_field():
    raw = config_from(
        "private.toml",
        **POCKET_ID
        | OBSERVABILITY
        | GRAFANA_OIDC
        | {"observability.grafana_oidc_client_secret": None},
    )
    with pytest.raises(
        ConfigError, match=r"partially configured.*\(missing: grafana_oidc_client_secret\)"
    ):
        _load_raw(raw)


def test_grafana_oidc_requires_observability():
    raw = config_from("private.toml", **POCKET_ID | GRAFANA_OIDC)
    with pytest.raises(ConfigError, match=r"grafana_oidc_client_id requires grafana_password"):
        _load_raw(raw)


def test_grafana_oidc_requires_pocket_id():
    raw = config_from("private.toml", **OBSERVABILITY | GRAFANA_OIDC)
    with pytest.raises(
        ConfigError, match=r"observability\.grafana_oidc_client_id requires pocket_id"
    ):
        _load_raw(raw)


def test_node_defaults_exported():
    data = _load_raw(config_from("private.toml")).model_dump(mode="json")
    node = data["nodes"][0]
    assert node["mtu"] == 1500
    assert node["secureboot"] is False
    assert node["kernel_modules"] == []


def test_gateways_may_leave_node_cidr_only_with_bgp():
    with_bgp = config_from("public.toml", **{"gateways.external": "192.168.50.1"})
    _load_raw(with_bgp)  # public.toml enables BGP
    without_bgp = config_from("private.toml", **{"gateways.external": "192.168.50.1"})
    with pytest.raises(ConfigError, match="required unless BGP is enabled"):
        _load_raw(without_bgp)


def test_schema_file_matches_model():
    committed = json.loads((REPO_ROOT / "cluster.schema.json").read_text())
    assert committed == schema(), "cluster.schema.json is stale: run `just template schema`"


def test_schema_omits_computed_fields():
    assert "cluster_issuer" not in schema()["properties"]


MATHERLYNET = POSTGRES_BACKUP | {
    "matherlynet.better_auth_secret": "fake",
    "matherlynet.admin_email": "admin@example.com",
}
GITHUB_OAUTH = {
    "matherlynet.github_client_id": "fake-github-client",
    "matherlynet.github_client_secret": "fake",
}


def test_matherlynet_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).matherlynet_enabled is False
    assert _load_raw(config_from("private.toml", **MATHERLYNET)).matherlynet_enabled is True


def test_partial_matherlynet_names_missing_field():
    raw = config_from("private.toml", **MATHERLYNET | {"matherlynet.admin_email": None})
    with pytest.raises(ConfigError, match=r"partially configured.*\(missing: admin_email\)"):
        _load_raw(raw)


def test_partial_matherlynet_oauth_names_missing_field():
    raw = config_from(
        "private.toml",
        **MATHERLYNET | GITHUB_OAUTH | {"matherlynet.github_client_secret": None},
    )
    with pytest.raises(
        ConfigError, match=r"partially configured.*\(missing: github_client_secret\)"
    ):
        _load_raw(raw)


def test_matherlynet_optional_fields_accepted():
    raw = config_from(
        "private.toml",
        **MATHERLYNET
        | GITHUB_OAUTH
        | {
            "matherlynet.smtp_url": "smtps://user:p%40ss@smtp.example.com:465",
            "matherlynet.mail_from": "matherlynet <noreply@example.com>",
            "matherlynet.playground": True,
        },
    )
    matherlynet = _load_raw(raw).matherlynet
    assert matherlynet.mail_from == "matherlynet <noreply@example.com>"
    assert matherlynet.github_client_id == "fake-github-client"
    assert matherlynet.playground is True


@pytest.mark.parametrize(
    "field, value",
    [
        ("smtp_url", "smtps://smtp.example.com"),
        ("mail_from", "noreply@example.com"),
        ("google_client_id", "fake"),
        ("playground", True),
    ],
)
def test_matherlynet_option_requires_section(field, value):
    overrides = {f"matherlynet.{field}": value}
    if field == "google_client_id":
        overrides["matherlynet.google_client_secret"] = "fake"
    raw = config_from("private.toml", **overrides)
    with pytest.raises(ConfigError, match=rf"{field} requires better_auth_secret and admin_email"):
        _load_raw(raw)


def test_matherlynet_smtp_url_must_be_a_url():
    raw = config_from("public.toml", **{"matherlynet.smtp_url": "smtp.example.com"})
    with pytest.raises(ConfigError, match=r"matherlynet\.smtp_url"):
        _load_raw(raw)


def test_matherlynet_mail_from_rejects_dollar():
    raw = config_from("private.toml", **MATHERLYNET | {"matherlynet.mail_from": "a$b@example.com"})
    with pytest.raises(ConfigError, match=r"matherlynet\.mail_from"):
        _load_raw(raw)


def test_matherlynet_requires_postgres_backup():
    raw = config_from(
        "private.toml",
        **{"matherlynet.better_auth_secret": "fake", "matherlynet.admin_email": "a@example.com"},
    )
    with pytest.raises(ConfigError, match=r"matherlynet requires postgres\.backup"):
        _load_raw(raw)


def test_matherlynet_requires_cloudflare_tunnel():
    raw = config_from("private.toml", **MATHERLYNET | {"ingress.mode": "direct"})
    with pytest.raises(
        ConfigError, match=r"matherlynet requires ingress\.mode 'cloudflare-tunnel'"
    ):
        _load_raw(raw)


def test_matherlynet_playground_requires_nvidia():
    raw = config_from("private.toml", **MATHERLYNET | {"matherlynet.playground": True})
    raw["nodes"][1]["kernel_modules"] = []
    with pytest.raises(ConfigError, match=r"matherlynet\.playground requires an NVIDIA node"):
        _load_raw(raw)


REACTIVE_RESUME = POCKET_ID | {
    "reactive_resume.auth_secret": "fake",
    "reactive_resume.encryption_secret": "x" * 32,
    "reactive_resume.oidc_client_id": "resume",
    "reactive_resume.oidc_client_secret": "fake",
    "reactive_resume.s3_endpoint": "https://fake.r2.cloudflarestorage.com",
    "reactive_resume.s3_bucket": "resume",
    "reactive_resume.s3_access_key_id": "fake",
    "reactive_resume.s3_secret_access_key": "fake",
}


def test_reactive_resume_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POCKET_ID)).reactive_resume_enabled is False
    raw = config_from("private.toml", **REACTIVE_RESUME)
    assert _load_raw(raw).reactive_resume_enabled is True


def test_partial_reactive_resume_names_missing_field():
    raw = config_from("private.toml", **REACTIVE_RESUME | {"reactive_resume.s3_bucket": None})
    with pytest.raises(
        ConfigError, match=r"reactive_resume is partially configured.*\(missing: s3_bucket\)"
    ):
        _load_raw(raw)


def test_reactive_resume_encryption_secret_needs_32_characters():
    raw = config_from(
        "private.toml", **REACTIVE_RESUME | {"reactive_resume.encryption_secret": "x" * 31}
    )
    with pytest.raises(ConfigError, match=r"reactive_resume\.encryption_secret"):
        _load_raw(raw)


def test_reactive_resume_requires_pocket_id():
    raw = config_from("private.toml", **REACTIVE_RESUME | {"pocket_id.encryption_key": None})
    with pytest.raises(ConfigError, match=r"reactive_resume requires pocket_id"):
        _load_raw(raw)


def test_reactive_resume_requires_ingress():
    raw = config_from("private.toml", **REACTIVE_RESUME | {"ingress.mode": "none"})
    with pytest.raises(ConfigError, match=r"reactive_resume requires ingress\.mode"):
        _load_raw(raw)


REDIS = {"redis.password": "x" * 24}


def test_redis_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).redis_enabled is False
    assert _load_raw(config_from("private.toml", **REDIS)).redis_enabled is True


@pytest.mark.parametrize("password", ["x" * 23, "x" * 23 + "@", "x" * 23 + "/"])
def test_redis_password_is_long_and_safe_in_a_url(password):
    raw = config_from("private.toml", **{"redis.password": password})
    with pytest.raises(ConfigError, match=r"redis\.password"):
        _load_raw(raw)


KENER = POSTGRES_BACKUP | REDIS | {"kener.secret_key": "x" * 32}
KENER_SMTP = KENER | {
    "kener.smtp_url": "smtps://user%40example.com:pass%2Fword@smtp.example.com",
    "kener.mail_from": "status@example.com",
}


def test_kener_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POSTGRES_BACKUP)).kener_enabled is False
    assert _load_raw(config_from("private.toml", **KENER)).kener_enabled is True


def test_kener_secret_key_needs_32_characters():
    raw = config_from("private.toml", **KENER | {"kener.secret_key": "x" * 31})
    with pytest.raises(ConfigError, match=r"kener\.secret_key"):
        _load_raw(raw)


def test_kener_requires_redis():
    raw = config_from("private.toml", **KENER | {"redis.password": None})
    with pytest.raises(ConfigError, match=r"kener requires redis\.password"):
        _load_raw(raw)


def test_kener_requires_postgres_backup():
    raw = config_from("private.toml", **REDIS | {"kener.secret_key": "x" * 32})
    with pytest.raises(ConfigError, match=r"kener requires postgres\.backup"):
        _load_raw(raw)


def test_kener_requires_ingress():
    raw = config_from("private.toml", **KENER | {"ingress.mode": "none"})
    with pytest.raises(ConfigError, match=r"kener requires ingress\.mode"):
        _load_raw(raw)


def test_kener_smtp_is_empty_when_unset():
    assert _load_raw(config_from("private.toml", **KENER)).kener_smtp == {}


def test_kener_smtp_splits_the_url_and_decodes_the_credentials():
    assert _load_raw(config_from("private.toml", **KENER_SMTP)).kener_smtp == {
        "host": "smtp.example.com",
        "port": "465",
        "user": "user@example.com",
        "password": "pass/word",
        "secure": "1",
    }
    plain = KENER_SMTP | {"kener.smtp_url": "smtp://u:p@smtp.example.com"}
    assert _load_raw(config_from("private.toml", **plain)).kener_smtp["port"] == "587"
    assert _load_raw(config_from("private.toml", **plain)).kener_smtp["secure"] == "0"
    custom = KENER_SMTP | {"kener.smtp_url": "smtp://u:p@smtp.example.com:2525"}
    assert _load_raw(config_from("private.toml", **custom)).kener_smtp["port"] == "2525"


def test_partial_kener_smtp_names_missing_field():
    raw = config_from("private.toml", **KENER_SMTP | {"kener.mail_from": None})
    with pytest.raises(ConfigError, match=r"kener is partially configured.*\(missing: mail_from\)"):
        _load_raw(raw)


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("smtp://smtp.example.com:587", "needs a user, a password and a host"),
        ("smtp://user@smtp.example.com", "needs a user, a password and a host"),
        ("smtp://u:p@smtp.example.com:port", "port that is not a number"),
        ("smtp://u:p%24word@smtp.example.com", "must not contain"),
    ],
)
def test_kener_smtp_url_is_rejected(url, message):
    raw = config_from("private.toml", **KENER_SMTP | {"kener.smtp_url": url})
    with pytest.raises(ConfigError, match=message):
        _load_raw(raw)


def test_kener_smtp_requires_secret_key():
    raw = config_from("private.toml", **KENER_SMTP | {"kener.secret_key": None})
    with pytest.raises(ConfigError, match=r"smtp_url requires secret_key"):
        _load_raw(raw)
