"""Unit tests for the cluster.toml validator.

Run from the repo root:
    uv run --locked pytest template/scripts/test_validate.py -q
"""

import json
import re
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import check_layout
import scaffold
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


def expected_error(fixture: Path) -> str:
    """The `# expect:` line every invalid fixture carries: the message its check raises."""
    for line in fixture.read_text().splitlines():
        if line.startswith("# expect: "):
            return line.removeprefix("# expect: ")
    raise AssertionError(f"{fixture.name} has no '# expect: <message>' line")


@pytest.mark.parametrize("fixture", INVALID, ids=lambda p: p.stem)
def test_invalid_fixture_rejected(fixture: Path):
    with pytest.raises(ConfigError, match=re.escape(expected_error(fixture))):
        load(str(fixture))


def _load_raw(raw: dict) -> Config:
    try:
        return Config.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(format_errors(e)) from None


def test_vault_is_required():
    assert _load_raw(config_from("single-node.toml")).onepassword_enabled is True
    for fixture in ("single-node.toml", "public.toml"):
        raw = config_from(fixture, **{"onepassword.vault": None})
        with pytest.raises(ConfigError, match=r"onepassword\.vault is required"):
            _load_raw(raw)


def test_ai_workspace_env_keys_are_unique():
    raw = config_from("public.toml", **{"ai_workspace.env_keys": ["A_KEY", "A_KEY"]})
    with pytest.raises(ConfigError, match="listed twice"):
        _load_raw(raw)


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
    raw = config_from(
        "public.toml",
        **{
            "matherlynet.playground": False,
            "localai.oidc_client_id": None,
        },
    )
    assert raw["nodes"][1]["kernel_modules"] == ["nvidia", "nvidia_uvm"]
    assert _load_raw(raw).nvidia_enabled is True
    raw["nodes"][1]["kernel_modules"] = ["nvidia_uvm"]
    assert _load_raw(raw).nvidia_enabled is False
    assert _load_raw(config_from("single-node.toml")).nvidia_enabled is False


def test_localai_webui_requires_nvidia():
    raw = config_from("public.toml", **{"matherlynet.playground": False})
    raw["nodes"][1]["kernel_modules"] = ["nvidia_uvm"]
    with pytest.raises(ConfigError, match="localai.oidc_client_id requires an NVIDIA node"):
        _load_raw(raw)


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
    cloudflare = config_from("public.toml", **{"ingress.mode": None})
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
}


def test_gates_read_booleans():
    cfg = _load_raw(config_from("public.toml", **{"kener.enabled": True}))
    assert cfg.kener_enabled is True
    assert _load_raw(config_from("private.toml", **POSTGRES_BACKUP)).kener_enabled is False


def test_rustfs_consumers_carry_no_keys():
    cfg = _load_raw(
        config_from("public.toml", **{"rustfs.enabled": True, "langfuse.enabled": True})
    )
    assert cfg.rustfs_consumers
    assert all(set(c) == {"name", "bucket"} for c in cfg.rustfs_consumers)


def test_tunnel_mode_requires_the_tunnel_id():
    raw = config_from("public.toml", **{"ingress.tunnel_id": None})
    with pytest.raises(ConfigError, match=r"ingress\.tunnel_id is required"):
        _load_raw(raw)
    assert _load_raw(config_from("public.toml")).ingress.tunnel_id == "fake"


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


@pytest.mark.parametrize("section", ["etcd_backup", "volume_backup"])
def test_bucket_backups_require_postgres_backup(section):
    assert getattr(_load_raw(config_from("private.toml")), f"{section}_enabled") is False
    on = config_from("private.toml", **POSTGRES_BACKUP | {f"{section}.enabled": True})
    assert getattr(_load_raw(on), f"{section}_enabled") is True
    with pytest.raises(ConfigError, match=rf"{section} requires postgres\.backup"):
        _load_raw(config_from("private.toml", **{f"{section}.enabled": True}))


OBSERVABILITY = {"observability.enabled": True}


def test_observability_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).observability_enabled is False
    assert _load_raw(config_from("private.toml", **OBSERVABILITY)).observability_enabled is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("discord", True),
        ("grafana_oidc_client_id", "grafana"),
        ("secret_key", True),
        ("sentry_org", "home"),
        ("proxmox_hosts", ["10.10.10.2"]),
    ],
)
def test_observability_option_requires_the_stack(field, value):
    raw = config_from("private.toml", **{f"observability.{field}": value})
    with pytest.raises(ConfigError, match=rf"{field} requires enabled"):
        _load_raw(raw)


def test_discord_accepted_with_observability():
    raw = config_from("private.toml", **OBSERVABILITY | {"observability.discord": True})
    assert _load_raw(raw).observability.discord is True


def test_heartbeat_requires_discord():
    raw = config_from("private.toml", **OBSERVABILITY | {"observability.heartbeat": True})
    with pytest.raises(ConfigError, match="heartbeat requires discord"):
        _load_raw(raw)
    raw["observability"]["discord"] = True
    assert _load_raw(raw).observability.heartbeat is True


UNIFI = {"unifi.host": "https://192.0.2.1"}


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


POCKET_ID = POSTGRES_BACKUP | {"pocket_id.enabled": True}
RADAR = POCKET_ID | {"radar.oidc_client_id": "fake"}


def test_pocket_id_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).pocket_id_enabled is False
    assert _load_raw(config_from("private.toml", **POCKET_ID)).pocket_id_enabled is True


def test_pocket_id_requires_postgres_backup():
    raw = config_from("private.toml", **{"pocket_id.enabled": True})
    with pytest.raises(ConfigError, match=r"pocket_id requires postgres\.backup"):
        _load_raw(raw)


def test_pocket_id_public_accepted_with_pocket_id():
    raw = config_from("private.toml", **POCKET_ID | {"pocket_id.public": True})
    assert _load_raw(raw).pocket_id.public is True


def test_pocket_id_public_requires_pocket_id():
    raw = config_from("private.toml", **{"pocket_id.public": True})
    with pytest.raises(ConfigError, match=r"pocket_id\.public requires pocket_id\.enabled"):
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


def test_radar_requires_pocket_id():
    raw = config_from("private.toml", **RADAR | {"pocket_id.enabled": None})
    with pytest.raises(ConfigError, match=r"radar requires pocket_id"):
        _load_raw(raw)


HUBBLE = POCKET_ID | {"cilium.hubble.oidc_client_id": "hubble"}


def test_hubble_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POCKET_ID)).hubble_enabled is False
    assert _load_raw(config_from("private.toml", **HUBBLE)).hubble_enabled is True


def test_hubble_requires_pocket_id():
    raw = config_from("private.toml", **HUBBLE | {"pocket_id.enabled": None})
    with pytest.raises(ConfigError, match=r"cilium\.hubble requires pocket_id"):
        _load_raw(raw)


GRAFANA_OIDC = {"observability.grafana_oidc_client_id": "grafana"}


def test_grafana_oidc_accepted_with_observability_and_pocket_id():
    raw = config_from("private.toml", **POCKET_ID | OBSERVABILITY | GRAFANA_OIDC)
    assert _load_raw(raw).observability.grafana_oidc_client_id == "grafana"


def test_grafana_oidc_requires_pocket_id():
    raw = config_from("private.toml", **OBSERVABILITY | GRAFANA_OIDC)
    with pytest.raises(
        ConfigError, match=r"observability\.grafana_oidc_client_id requires pocket_id"
    ):
        _load_raw(raw)


GITHUB_APP = {
    "observability.github_app_id": "123456",
    "observability.github_app_installation_id": "7890123",
}


def test_github_app_accepted_with_observability():
    raw = config_from("private.toml", **OBSERVABILITY | GITHUB_APP)
    assert _load_raw(raw).observability.github_app_id == "123456"


def test_partial_github_app_names_missing_field():
    raw = config_from(
        "private.toml",
        **OBSERVABILITY | GITHUB_APP | {"observability.github_app_installation_id": None},
    )
    with pytest.raises(
        ConfigError, match=r"partially configured.*\(missing: github_app_installation_id\)"
    ):
        _load_raw(raw)


def test_github_app_requires_observability():
    raw = config_from("private.toml", **GITHUB_APP)
    with pytest.raises(ConfigError, match=r"github_app_id requires enabled"):
        _load_raw(raw)


def test_sentry_accepted_with_observability_and_url_defaults():
    raw = config_from("private.toml", **OBSERVABILITY | {"observability.sentry_org": "home"})
    observability = _load_raw(raw).observability
    assert observability.sentry_org == "home"
    assert observability.sentry_url == "https://sentry.io"


def test_sentry_url_must_be_a_host():
    raw = config_from(
        "private.toml",
        **OBSERVABILITY
        | {"observability.sentry_org": "home", "observability.sentry_url": "https://sentry.io/org"},
    )
    with pytest.raises(ConfigError, match=r"observability\.sentry_url"):
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


MATHERLYNET = POSTGRES_BACKUP | {"matherlynet.enabled": True}
GITHUB_OAUTH = {"matherlynet.github_client_id": "fake-github-client", "matherlynet.github": True}


def test_matherlynet_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).matherlynet_enabled is False
    assert _load_raw(config_from("private.toml", **MATHERLYNET)).matherlynet_enabled is True


@pytest.mark.parametrize("dropped", ["github_client_id", "github"])
def test_partial_matherlynet_oauth_names_missing_field(dropped):
    raw = config_from(
        "private.toml", **MATHERLYNET | GITHUB_OAUTH | {f"matherlynet.{dropped}": None}
    )
    with pytest.raises(ConfigError, match=rf"partially configured.*\(missing: {dropped}\)"):
        _load_raw(raw)


def test_matherlynet_optional_fields_accepted():
    raw = config_from(
        "private.toml",
        **MATHERLYNET
        | GITHUB_OAUTH
        | {"matherlynet.smtp": True, "matherlynet.mail": True, "matherlynet.playground": True},
    )
    matherlynet = _load_raw(raw).matherlynet
    assert (matherlynet.smtp, matherlynet.mail, matherlynet.github) == (True, True, True)
    assert matherlynet.github_client_id == "fake-github-client"
    assert matherlynet.playground is True


@pytest.mark.parametrize(
    "field, value",
    [("smtp", True), ("mail", True), ("google_client_id", "fake"), ("playground", True)],
)
def test_matherlynet_option_requires_section(field, value):
    overrides = {f"matherlynet.{field}": value}
    if field == "google_client_id":
        overrides["matherlynet.google"] = True
    raw = config_from("private.toml", **overrides)
    with pytest.raises(ConfigError, match=rf"{field} requires enabled"):
        _load_raw(raw)


def test_matherlynet_requires_postgres_backup():
    raw = config_from("private.toml", **{"matherlynet.enabled": True})
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
    "reactive_resume.enabled": True,
    "reactive_resume.oidc_client_id": "resume",
    "reactive_resume.s3_bucket": "resume",
}


def test_reactive_resume_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POCKET_ID)).reactive_resume_enabled is False
    raw = config_from("private.toml", **REACTIVE_RESUME)
    assert _load_raw(raw).reactive_resume_enabled is True


@pytest.mark.parametrize("dropped", ["enabled", "oidc_client_id", "s3_bucket"])
def test_partial_reactive_resume_names_missing_field(dropped):
    raw = config_from("private.toml", **REACTIVE_RESUME | {f"reactive_resume.{dropped}": None})
    with pytest.raises(
        ConfigError, match=rf"reactive_resume is partially configured.*\(missing: {dropped}\)"
    ):
        _load_raw(raw)


def test_reactive_resume_requires_pocket_id():
    raw = config_from("private.toml", **REACTIVE_RESUME | {"pocket_id.enabled": None})
    with pytest.raises(ConfigError, match=r"reactive_resume requires pocket_id"):
        _load_raw(raw)


def test_reactive_resume_requires_ingress():
    raw = config_from("private.toml", **REACTIVE_RESUME | {"ingress.mode": "none"})
    with pytest.raises(ConfigError, match=r"reactive_resume requires ingress\.mode"):
        _load_raw(raw)


REDIS = {"redis.enabled": True}


def test_redis_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).redis_enabled is False
    assert _load_raw(config_from("private.toml", **REDIS)).redis_enabled is True


KENER = POSTGRES_BACKUP | REDIS | {"kener.enabled": True}


def test_kener_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POSTGRES_BACKUP)).kener_enabled is False
    assert _load_raw(config_from("private.toml", **KENER)).kener_enabled is True


def test_kener_requires_redis():
    raw = config_from("private.toml", **KENER | {"redis.enabled": None})
    with pytest.raises(ConfigError, match=r"kener requires redis"):
        _load_raw(raw)


def test_kener_requires_postgres_backup():
    raw = config_from("private.toml", **REDIS | {"kener.enabled": True})
    with pytest.raises(ConfigError, match=r"kener requires postgres\.backup"):
        _load_raw(raw)


def test_kener_requires_ingress():
    raw = config_from("private.toml", **KENER | {"ingress.mode": "none"})
    with pytest.raises(ConfigError, match=r"kener requires ingress\.mode"):
        _load_raw(raw)


def test_kener_smtp_follows_the_flag_and_requires_kener():
    assert _load_raw(config_from("private.toml", **KENER)).kener_smtp is False
    assert _load_raw(config_from("private.toml", **KENER | {"kener.smtp": True})).kener_smtp is True
    with pytest.raises(ConfigError, match=r"smtp requires enabled"):
        _load_raw(config_from("private.toml", **{"kener.smtp": True}))


NETWORK_OPTIMIZER = OBSERVABILITY | {"network_optimizer.enabled": True}
NETWORK_OPTIMIZER_OIDC = (
    NETWORK_OPTIMIZER | POCKET_ID | {"network_optimizer.oidc_client_id": "network-optimizer"}
)


def test_network_optimizer_flags():
    off = _load_raw(config_from("private.toml", **OBSERVABILITY))
    assert (off.network_optimizer_enabled, off.network_optimizer_oidc) == (False, False)
    on = _load_raw(config_from("private.toml", **NETWORK_OPTIMIZER))
    assert (on.network_optimizer_enabled, on.network_optimizer_oidc) == (True, False)
    oidc = _load_raw(config_from("private.toml", **NETWORK_OPTIMIZER_OIDC))
    assert (oidc.network_optimizer_enabled, oidc.network_optimizer_oidc) == (True, True)


def test_network_optimizer_requires_observability():
    raw = config_from("private.toml", **{"network_optimizer.enabled": True})
    with pytest.raises(ConfigError, match=r"network_optimizer requires observability"):
        _load_raw(raw)


def test_network_optimizer_oidc_requires_pocket_id():
    raw = config_from("private.toml", **NETWORK_OPTIMIZER_OIDC | {"pocket_id.enabled": None})
    with pytest.raises(ConfigError, match=r"network_optimizer\.oidc_client_id requires pocket_id"):
        _load_raw(raw)


def test_network_optimizer_oidc_requires_the_app():
    raw = config_from(
        "private.toml", **NETWORK_OPTIMIZER_OIDC | {"network_optimizer.enabled": None}
    )
    with pytest.raises(ConfigError, match=r"oidc_client_id requires enabled"):
        _load_raw(raw)


PEGAPROX_METRICS = OBSERVABILITY | {"pegaprox.enabled": True, "pegaprox.metrics": True}


def test_pegaprox_flags():
    assert not _load_raw(config_from("private.toml")).pegaprox_enabled
    on = _load_raw(config_from("private.toml", **{"pegaprox.enabled": True}))
    assert (on.pegaprox_enabled, on.pegaprox_metrics) == (True, False)
    assert _load_raw(config_from("private.toml", **PEGAPROX_METRICS)).pegaprox_metrics is True


def test_pegaprox_metrics_requires_observability():
    raw = config_from("private.toml", **{"pegaprox.enabled": True, "pegaprox.metrics": True})
    with pytest.raises(ConfigError, match=r"pegaprox\.metrics requires observability"):
        _load_raw(raw)


def test_pegaprox_metrics_requires_pegaprox():
    raw = config_from("private.toml", **PEGAPROX_METRICS | {"pegaprox.enabled": None})
    with pytest.raises(ConfigError, match=r"metrics requires enabled"):
        _load_raw(raw)


ACTUAL_BUDGET = POCKET_ID | {"actual_budget.oidc_client_id": "fake"}


def test_actual_budget_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POCKET_ID)).actual_budget_enabled is False
    assert _load_raw(config_from("private.toml", **ACTUAL_BUDGET)).actual_budget_enabled is True


def test_actual_budget_requires_pocket_id():
    raw = config_from("private.toml", **ACTUAL_BUDGET | {"pocket_id.enabled": None})
    with pytest.raises(ConfigError, match=r"actual_budget requires pocket_id"):
        _load_raw(raw)


def test_actual_budget_public_requires_client():
    raw = config_from("private.toml", **POCKET_ID | {"actual_budget.public": True})
    with pytest.raises(ConfigError, match=r"actual_budget\.public requires oidc_client_id"):
        _load_raw(raw)


def test_actual_budget_public_requires_public_pocket_id():
    raw = config_from("private.toml", **ACTUAL_BUDGET | {"actual_budget.public": True})
    with pytest.raises(ConfigError, match=r"actual_budget\.public requires pocket_id\.public"):
        _load_raw(raw)


CLIPROXYAPI = {"cliproxyapi.enabled": True}


def test_cliproxyapi_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).cliproxyapi_enabled is False
    assert _load_raw(config_from("private.toml", **CLIPROXYAPI)).cliproxyapi_enabled is True


def test_ohmycpa_enabled_by_its_flag():
    assert _load_raw(config_from("private.toml", **CLIPROXYAPI)).ohmycpa_enabled is False
    raw = config_from("private.toml", **CLIPROXYAPI, **{"cliproxyapi.ohmycpa": True})
    assert _load_raw(raw).ohmycpa_enabled is True


@pytest.mark.parametrize("field", ["ohmycpa", "github"])
def test_cliproxyapi_option_needs_cliproxyapi(field):
    raw = config_from("private.toml", **{f"cliproxyapi.{field}": True})
    with pytest.raises(ConfigError, match=rf"cliproxyapi\.{field} needs enabled"):
        _load_raw(raw)


FIRECRAWL = CLIPROXYAPI | REDIS | {"firecrawl.enabled": True}


def test_firecrawl_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).firecrawl_enabled is False
    assert _load_raw(config_from("private.toml", **FIRECRAWL)).firecrawl_enabled is True


def test_firecrawl_needs_cliproxyapi():
    raw = config_from("private.toml", **REDIS, **{"firecrawl.enabled": True})
    with pytest.raises(ConfigError, match="firecrawl requires cliproxyapi"):
        _load_raw(raw)


def test_firecrawl_needs_redis():
    raw = config_from("private.toml", **CLIPROXYAPI, **{"firecrawl.enabled": True})
    with pytest.raises(ConfigError, match="firecrawl requires redis"):
        _load_raw(raw)


def test_firecrawl_model_needs_enabled():
    raw = config_from("private.toml", **{"firecrawl.model": "claude-haiku-5-5"})
    with pytest.raises(ConfigError, match=r"firecrawl\.model requires enabled"):
        _load_raw(raw)


VOLUME_BACKUP = POSTGRES_BACKUP | {"volume_backup.enabled": True}
CAREER_OPS = (
    POCKET_ID
    | VOLUME_BACKUP
    | {
        "career_ops.enabled": True,
        "career_ops.oidc_client_id": "fake",
        "career_ops.publish_oidc_client_id": "fake-publish",
    }
)


def test_career_ops_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).career_ops_enabled is False
    assert _load_raw(config_from("private.toml", **CAREER_OPS)).career_ops_enabled is True


def test_partial_career_ops_names_missing_field():
    raw = config_from("private.toml", **CAREER_OPS | {"career_ops.publish_oidc_client_id": None})
    with pytest.raises(
        ConfigError,
        match=r"career_ops is partially configured.*\(missing: publish_oidc_client_id\)",
    ):
        _load_raw(raw)


PROXY = {
    "career_ops.claude_credential": "proxy",
    "career_ops.anthropic_base_url": "http://cliproxyapi.llms.svc.cluster.local:8317",
}


def test_career_ops_claude_credential_defaults_to_oauth():
    assert _load_raw(config_from("private.toml", **CAREER_OPS)).career_ops.claude_credential == (
        "oauth"
    )
    career_ops = _load_raw(config_from("private.toml", **CAREER_OPS | PROXY)).career_ops
    assert career_ops.claude_credential == "proxy"


@pytest.mark.parametrize("dropped", list(PROXY))
def test_career_ops_proxy_needs_the_credential_and_the_url(dropped):
    raw = config_from("private.toml", **CAREER_OPS | PROXY | {dropped: None})
    with pytest.raises(ConfigError, match=r"claude_credential 'proxy' and anthropic_base_url"):
        _load_raw(raw)


def test_career_ops_proxy_url_needs_no_trailing_slash():
    raw = config_from(
        "private.toml",
        **CAREER_OPS | PROXY | {"career_ops.anthropic_base_url": "http://cliproxyapi:8317/"},
    )
    with pytest.raises(ConfigError, match=r"anthropic_base_url"):
        _load_raw(raw)


@pytest.mark.parametrize(
    ("field", "value"), [("publish", True), ("anthropic_base_url", "http://cliproxyapi:8317")]
)
def test_career_ops_option_needs_the_section(field, value):
    raw = config_from("private.toml", **{f"career_ops.{field}": value})
    with pytest.raises(ConfigError, match=rf"career_ops\.{field} requires enabled"):
        _load_raw(raw)
    assert _load_raw(config_from("private.toml", **CAREER_OPS)).career_ops.publish is False


def test_career_ops_requires_pocket_id():
    raw = config_from("private.toml", **CAREER_OPS | {"pocket_id.enabled": None})
    with pytest.raises(ConfigError, match=r"career_ops requires pocket_id"):
        _load_raw(raw)


def test_career_ops_requires_volume_backup():
    raw = config_from("private.toml", **CAREER_OPS)
    del raw["volume_backup"]
    with pytest.raises(ConfigError, match=r"career_ops requires volume_backup"):
        _load_raw(raw)


def test_career_ops_requires_ingress():
    raw = config_from("private.toml", **CAREER_OPS | {"ingress.mode": "none"})
    with pytest.raises(ConfigError, match=r"career_ops requires ingress\.mode 'cloudflare-tunnel'"):
        _load_raw(raw)


def test_career_ops_public_requires_public_pocket_id():
    raw = config_from("private.toml", **CAREER_OPS | {"career_ops.public": True})
    with pytest.raises(ConfigError, match=r"career_ops\.public requires pocket_id\.public"):
        _load_raw(raw)
    raw = config_from("private.toml", **{"career_ops.public": True})
    with pytest.raises(ConfigError, match=r"career_ops\.public requires enabled"):
        _load_raw(raw)


MEDIA = POCKET_ID | {
    "media.nfs_server": "10.10.10.50",
    "media.node": "k8s-1",
    "media.oidc_client_id": "fake",
}


def test_media_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml")).media_enabled is False
    blank = config_from("private.toml", **{"media.nfs_server": ""})
    assert _load_raw(blank).media_enabled is False
    assert _load_raw(config_from("private.toml", **MEDIA)).media_enabled is True
    assert _load_raw(config_from("private.toml", **MEDIA)).media_plex_enabled is False
    with_plex = MEDIA | {"media.plex_host": "10.10.10.60"}
    assert _load_raw(config_from("private.toml", **with_plex)).media_plex_enabled is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("recyclarr", True),
        ("nfs_share", "/tank/media"),
        ("timezone", "America/Chicago"),
        ("keys_revision", 1),
    ],
)
def test_media_field_requires_nfs_server(field, value):
    raw = config_from("private.toml", **{f"media.{field}": value})
    with pytest.raises(ConfigError, match=rf"{field} requires nfs_server"):
        _load_raw(raw)


def test_media_nfs_server_requires_the_rest():
    raw = config_from("private.toml", **POCKET_ID | {"media.nfs_server": "10.10.10.50"})
    with pytest.raises(ConfigError, match=r"media requires node and oidc_client_id"):
        _load_raw(raw)


def test_media_requires_pocket_id():
    raw = config_from("private.toml", **MEDIA | {"pocket_id.enabled": None})
    with pytest.raises(ConfigError, match=r"media requires pocket_id"):
        _load_raw(raw)


@pytest.mark.parametrize("node", ["k8s-0", "k8s-9"])
def test_media_node_must_be_a_worker(node):
    raw = config_from("private.toml", **MEDIA | {"media.node": node})
    with pytest.raises(ConfigError, match=rf"media\.node {node} must name a \[\[nodes\]\] entry"):
        _load_raw(raw)


def test_media_public_requires_public_pocket_id():
    raw = config_from("private.toml", **MEDIA | {"media.public": True})
    with pytest.raises(ConfigError, match=r"media\.public requires pocket_id\.public"):
        _load_raw(raw)


AI_WORKSPACE = POCKET_ID | {"ai_workspace.oidc_client_id": "fake"}


def test_ai_workspace_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POCKET_ID)).ai_workspace_enabled is False
    assert _load_raw(config_from("private.toml", **AI_WORKSPACE)).ai_workspace_enabled is True


def test_ai_workspace_requires_pocket_id():
    raw = config_from("private.toml", **AI_WORKSPACE | {"pocket_id.enabled": None})
    with pytest.raises(ConfigError, match=r"ai_workspace requires pocket_id"):
        _load_raw(raw)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allowlist", True),
        ("admins", True),
        ("browsing", True),
        ("public", True),
        ("env_keys", ["ANTHROPIC_API_KEY"]),
    ],
)
def test_ai_workspace_options_require_client(field, value):
    raw = config_from("private.toml", **POCKET_ID | {f"ai_workspace.{field}": value})
    with pytest.raises(ConfigError, match=rf"ai_workspace\.{field} requires oidc_client_id"):
        _load_raw(raw)


def test_ai_workspace_public_requires_public_pocket_id():
    raw = config_from("private.toml", **AI_WORKSPACE | {"ai_workspace.public": True})
    with pytest.raises(ConfigError, match=r"ai_workspace\.public requires pocket_id\.public"):
        _load_raw(raw)


@pytest.mark.parametrize(
    "key",
    [
        "LOCALAI_API_HOST",
        "LOCALAI_API_KEY",
        "AUTH_SECRET",
        "PUPPETEER_WSS_ENDPOINT",
        "lowercase_key",
    ],
)
def test_ai_workspace_env_keys_reject_reserved_and_malformed_names(key):
    raw = config_from("private.toml", **AI_WORKSPACE | {"ai_workspace.env_keys": [key]})
    with pytest.raises(ConfigError, match=r"ai_workspace"):
        _load_raw(raw)


def test_ai_workspace_env_keys_accept_the_button_label():
    raw = config_from(
        "private.toml", **AI_WORKSPACE | {"ai_workspace.env_keys": ["AUTH_OIDC_NAME"]}
    )
    assert _load_raw(raw).ai_workspace.env_keys == ["AUTH_OIDC_NAME"]


AI_KB = POSTGRES_BACKUP | REDIS | {"ai_kb.enabled": True, "ai_kb.admin_email": "admin@example.com"}


def test_ai_kb_enabled_only_when_configured():
    assert _load_raw(config_from("private.toml", **POSTGRES_BACKUP | REDIS)).ai_kb_enabled is False
    assert _load_raw(config_from("private.toml", **AI_KB)).ai_kb_enabled is True


def test_ai_kb_needs_its_admin_email():
    raw = config_from("private.toml", **AI_KB | {"ai_kb.admin_email": None})
    with pytest.raises(ConfigError, match=r"ai_kb is partially configured.*admin_email"):
        _load_raw(raw)


AI_KB_OIDC = AI_KB | {"ai_kb.oidc_client_id": "ai-kb"}


def test_ai_kb_oidc_requires_pocket_id():
    raw = config_from("private.toml", **AI_KB_OIDC)
    with pytest.raises(ConfigError, match=r"ai_kb\.oidc_client_id requires pocket_id"):
        _load_raw(raw)
    assert _load_raw(config_from("private.toml", **AI_KB_OIDC | POCKET_ID)).ai_kb_oidc is True


def test_ai_kb_requires_ingress():
    raw = config_from("private.toml", **AI_KB | {"ingress.mode": "none"})
    with pytest.raises(ConfigError, match=r"ai_kb requires ingress\.mode"):
        _load_raw(raw)


RUSTFS = {"rustfs.enabled": True, "rustfs.node": "k8s-1"}
AI_KB_RUSTFS = AI_KB | {"ai_kb.rustfs": True}


def test_rustfs_needs_its_node():
    with pytest.raises(ConfigError, match=r"rustfs is partially configured.*\(missing: node\)"):
        _load_raw(config_from("private.toml", **{"rustfs.enabled": True}))
    with pytest.raises(ConfigError, match=r"rustfs\.node k8s-0 must name"):
        _load_raw(config_from("private.toml", **RUSTFS | {"rustfs.node": "k8s-0"}))


def test_rustfs_consumers_lists_ai_kb_when_its_flag_is_set():
    assert _load_raw(config_from("private.toml", **RUSTFS)).rustfs_consumers == []
    config = _load_raw(config_from("private.toml", **RUSTFS | AI_KB_RUSTFS))
    assert config.rustfs_consumers == [{"name": "ai-kb", "bucket": "ai-kb-files"}]


def test_ai_kb_rustfs_requires_the_rest_of_the_section():
    with pytest.raises(ConfigError, match=r"ai_kb\.rustfs requires the rest of \[ai_kb\]"):
        _load_raw(config_from("private.toml", **RUSTFS | {"ai_kb.rustfs": True}))


def test_ai_kb_rustfs_requires_rustfs():
    with pytest.raises(ConfigError, match=r"ai_kb\.rustfs requires rustfs"):
        _load_raw(config_from("private.toml", **AI_KB_RUSTFS))


LANGFUSE = (
    POCKET_ID | REDIS | RUSTFS | {"langfuse.enabled": True, "langfuse.oidc_client_id": "langfuse"}
)


def test_rustfs_consumers_lists_langfuse_when_it_is_enabled():
    config = _load_raw(config_from("private.toml", **LANGFUSE))
    assert config.langfuse_enabled
    assert config.rustfs_consumers == [{"name": "langfuse", "bucket": "langfuse-events"}]


def test_rustfs_consumers_lists_itsaplan_when_it_is_enabled():
    raw = config_from("private.toml", **POSTGRES_BACKUP | RUSTFS | {"itsaplan.enabled": True})
    assert _load_raw(raw).rustfs_consumers == [
        {"name": "itsaplan", "bucket": "itsaplan-attachments"}
    ]
    with pytest.raises(ConfigError, match=r"itsaplan requires rustfs"):
        _load_raw(config_from("private.toml", **POSTGRES_BACKUP | {"itsaplan.enabled": True}))


@pytest.mark.parametrize(
    ("dropped", "message"),
    [
        (REDIS, r"langfuse requires redis"),
        (POCKET_ID.keys() - POSTGRES_BACKUP.keys(), r"langfuse\.oidc_client_id requires pocket_id"),
        (RUSTFS, r"langfuse requires rustfs"),
    ],
)
def test_langfuse_requires_its_datastores_and_login(dropped, message):
    raw = {key: value for key, value in LANGFUSE.items() if key not in dropped}
    with pytest.raises(ConfigError, match=message):
        _load_raw(config_from("private.toml", **raw))


def test_ai_kb_tracing_requires_langfuse():
    with pytest.raises(ConfigError, match=r"ai_kb\.tracing requires langfuse"):
        _load_raw(config_from("private.toml", **AI_KB | {"ai_kb.tracing": True}))
    config = _load_raw(config_from("private.toml", **LANGFUSE | AI_KB | {"ai_kb.tracing": True}))
    assert config.ai_kb_tracing


@pytest.mark.parametrize("field", ["tracing", "neo4j", "searxng"])
def test_ai_kb_option_requires_the_rest_of_the_section(field):
    with pytest.raises(ConfigError, match=rf"ai_kb\.{field} requires the rest of \[ai_kb\]"):
        _load_raw(config_from("private.toml", **LANGFUSE | {f"ai_kb.{field}": True}))


def test_ai_kb_neo4j_and_searxng_follow_their_flags():
    config = _load_raw(
        config_from("private.toml", **AI_KB | {"ai_kb.neo4j": True, "ai_kb.searxng": True})
    )
    assert (config.ai_kb_neo4j, config.ai_kb_searxng) == (True, True)
    assert _load_raw(config_from("private.toml", **AI_KB)).ai_kb_neo4j is False


def test_langfuse_is_all_or_none():
    raw = POCKET_ID | REDIS | RUSTFS | {"langfuse.enabled": True}
    with pytest.raises(ConfigError, match=r"langfuse is partially configured"):
        _load_raw(config_from("private.toml", **raw))


SAMPLE_TABLES = list(tomllib.loads((REPO_ROOT / "cluster.sample.toml").read_text()))


@pytest.mark.parametrize("fixture", VALID, ids=lambda p: p.stem)
def test_valid_fixture_follows_sample_layout(fixture):
    tables = list(tomllib.loads(fixture.read_text()))
    assert check_layout.misplaced(SAMPLE_TABLES, tables) is None


@pytest.mark.parametrize(
    "config",
    ["[a.sub]\nx = 1\n\n[c]\ny = 2\n", "[a]\nx = 1\n\n[a.sub]\nz = 3\n\n[c]\ny = 2\n"],
)
def test_scaffold_lands_after_a_table_with_dotted_headers(tmp_path, config):
    sample = tmp_path / "sample.toml"
    sample.write_text("[a]\nx = 1\n\n[a.sub]\nz = 3\n\n[b]\n# k = 1\n\n[c]\ny = 2\n")
    target = tmp_path / "config.toml"
    target.write_text(config)
    assert scaffold.main("b", str(sample), str(target)) == 0
    tables = list(tomllib.loads(target.read_text()))
    assert check_layout.misplaced(["a", "b", "c"], tables) is None
    assert tables == ["a", "b", "c"]


def test_misplaced_table_is_named():
    assert check_layout.misplaced(["a", "b", "c"], ["a", "c", "b"]) == ("c", "b")
    assert check_layout.misplaced(["a", "b", "c"], ["a", "c", "nodes"]) is None


def test_private_cidrs_cover_reserved_ranges():
    config = _load_raw(config_from("public.toml"))
    cidrs = set(config.private_cidrs)
    for want in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "169.254.0.0/16",
        "127.0.0.0/8",
        "0.0.0.0/8",
        "192.0.0.0/24",
        "198.18.0.0/15",
        "224.0.0.0/4",
        "240.0.0.0/4",
    ):
        assert want in cidrs
    assert str(config.kubernetes.pod_cidr) in cidrs


@pytest.mark.parametrize("flag", ["web_push", "git_webhooks"])
def test_itsaplan_flags_need_the_app(flag):
    raw = config_from("internal.toml", **{f"itsaplan.{flag}": True})
    with pytest.raises(ConfigError, match=f"itsaplan.{flag} requires itsaplan.enabled"):
        _load_raw(raw)


def test_itsaplan_git_webhooks_need_an_ingress():
    raw = config_from("internal.toml", **{"itsaplan.enabled": True, "itsaplan.git_webhooks": True})
    with pytest.raises(ConfigError, match="itsaplan.git_webhooks requires ingress.mode other"):
        _load_raw(raw)
