"""Unit tests for the 1Password secret map and secrets-check.

Run from the repo root:
    uv run --locked pytest template/scripts/test_secret_map.py -q
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from pydantic import BaseModel
from secret_map import ENTRIES, GATES, MOVING_PATHS, items, lookup
from secrets_check import check
from validate import Config, load

REPO_ROOT = Path(__file__).parents[2]
FULL = REPO_ROOT / ".github/template-tests/valid/public.toml"
CFG = {"kener_enabled": True, "etcd_backup_enabled": True}


def dotted_paths(model: type[BaseModel], prefix: str = "") -> set[str]:
    paths = set()
    for name, field in model.model_fields.items():
        nested = field.annotation
        if isinstance(nested, type) and issubclass(nested, BaseModel):
            paths |= dotted_paths(nested, f"{prefix}{name}.")
        else:
            paths.add(prefix + name)
    return paths


def test_no_moving_path_remains():
    assert not (MOVING_PATHS & dotted_paths(Config))


def test_every_requirement_is_a_gate_or_a_config_path():
    config = load(str(FULL))
    unknown = [
        e.requires
        for e in ENTRIES
        if e.requires not in GATES and lookup(config, e.requires) is None
    ]
    assert not unknown


def test_full_fixture_requires_every_field():
    """The fixture that turns everything on needs every mapped field but the proxy key."""
    config = load(str(FULL))
    missing = {p.removesuffix(": missing") for p in check({}, config)}
    mapped = {f"{e.item}/{e.field}" for e in ENTRIES if e.field != "*"}
    assert mapped - missing == {"career-ops/ANTHROPIC_AUTH_TOKEN"}
    assert "ai-workspace-env/ANTHROPIC_API_KEY" in missing


def test_labels_are_unique_and_have_no_spaces():
    for item, entries in items().items():
        labels = [e.field for e in entries]
        assert len(labels) == len(set(labels)), item
        assert not [label for label in labels if " " in label], item


def test_missing_field_is_reported():
    assert "kener/SECRET_KEY: missing" in check({"kener": []}, CFG)


def test_missing_item_is_reported():
    assert "kener/SECRET_KEY: missing" in check({}, CFG)


def test_disabled_feature_needs_nothing():
    assert not [p for p in check({}, {}) if p.startswith("kener/")]


# The all-or-none and "X is required" rules validate.py held while the secret was in cluster.toml.
@pytest.mark.parametrize(
    ("config", "field"),
    [
        ({"dns": {"provider": "cloudflare"}}, "dns/TOKEN"),
        ({"nvidia_enabled": True}, "localai/API_KEY"),
        ({"hubble_enabled": True}, "cilium-hubble/OIDC_CLIENT_SECRET"),
        ({"localai_webui_enabled": True}, "localai/OIDC_CLIENT_SECRET"),
        ({"postgres_backup_enabled": True}, "postgres-backup/SECRET_ACCESS_KEY"),
        ({"etcd_backup_enabled": True}, "etcd-backup/SECRET_KEY"),
        ({"volume_backup_enabled": True}, "volume-backup/SECRET_KEY"),
        ({"observability_enabled": True}, "observability/INFLUXDB_TOKEN"),
        (
            {"observability": {"grafana_oidc_client_id": "grafana"}},
            "observability/GRAFANA_OIDC_CLIENT_SECRET",
        ),
        ({"observability": {"github_app_id": "1"}}, "observability/GITHUB_APP_PRIVATE_KEY"),
        ({"observability": {"sentry_org": "home"}}, "observability/SENTRY_TOKEN"),
        ({"unifi_dns_enabled": True}, "unifi/API_KEY"),
        ({"radar_enabled": True}, "radar/OIDC_CLIENT_SECRET"),
        ({"matherlynet_enabled": True}, "matherlynet/ADMIN_EMAIL"),
        ({"matherlynet": {"github": True}}, "matherlynet/GITHUB_CLIENT_SECRET"),
        ({"reactive_resume_enabled": True}, "reactive-resume/S3_SECRET_ACCESS_KEY"),
        ({"kener_smtp": True}, "kener/MAIL_FROM"),
        ({"kener_smtp": True}, "kener/SMTP_HOST"),
        ({"kener_smtp": True}, "kener/SMTP_USER"),
        ({"kener_smtp": True}, "kener/SMTP_PASS"),
        ({"network_optimizer_oidc": True}, "network-optimizer/OIDC_CLIENT_SECRET"),
        ({"actual_budget_enabled": True}, "actual-budget/OIDC_CLIENT_SECRET"),
        ({"media_enabled": True}, "media/SABNZBD_NZB_KEY"),
        ({"media_plex_enabled": True}, "media/PLEX_TOKEN"),
        ({"ai_workspace_enabled": True}, "ai-workspace/AUTH_SECRET"),
        ({"ai_kb_enabled": True}, "ai-kb/AES_KEY"),
        ({"ai_kb_rustfs": True}, "ai-kb/RUSTFS_SECRET_KEY"),
        ({"rustfs_enabled": True}, "rustfs/SECRET_KEY"),
        ({"langfuse_enabled": True}, "langfuse/SALT"),
        ({"itsaplan_enabled": True}, "itsaplan/APP_ENCRYPTION_KEY"),
        ({"cliproxyapi_enabled": True}, "cliproxyapi/API_KEY"),
        ({"career_ops_enabled": True}, "career-ops/PUBLISH_ALLOWED_EMAILS"),
    ],
)
def test_enabled_feature_needs_its_fields(config, field):
    assert f"{field}: missing" in check({}, config)
    assert f"{field}: missing" not in check({}, {})


def test_bad_label_is_reported():
    f = {"label": "SECRET_KEY", "value": "x" * 32}
    assert "kener/SECRET_KEY: duplicate label" in check({"kener": [f, f]}, CFG)
    g = {"label": "SECRET KEY", "value": "x" * 32}
    assert "kener/SECRET KEY: label has a space" in check({"kener": [g]}, CFG)


def test_pattern_rules_are_enforced():
    f = {"label": "ACCESS_KEY", "value": "bad key$"}
    assert "etcd-backup/ACCESS_KEY: pattern" in check({"etcd-backup": [f]}, CFG)


# One malformed value per format rule validate.py held on a field that moved.
@pytest.mark.parametrize(
    ("item", "label", "value"),
    [
        ("ai-kb", "AES_KEY", "a" * 31),
        ("ai-workspace", "AUTH_SECRET", "x" * 31),
        ("ai-workspace", "BROWSING_TOKEN", "a" * 31 + "-"),
        ("ai-workspace", "ALLOWED_EMAILS", "family.example"),
        ("ai-workspace", "ADMIN_EMAILS", "@example.com"),
        ("etcd-backup", "SECRET_KEY", "a/b"),
        ("volume-backup", "SECRET_KEY", "a@b"),
        ("langfuse", "ENCRYPTION_KEY", "z" * 64),
        ("pegaprox", "DB_KEY", "tooshort"),
        ("reactive-resume", "AUTH_SECRET", "x" * 31),
        ("rustfs", "SECRET_KEY", "s" * 31),
        ("redis", "PASSWORD", "x" * 23 + "@"),
        ("network-optimizer", "APP_PASSWORD", "fakefake"),
        ("pocket-id", "ENCRYPTION_KEY", "fifteen-chars-x"),
        ("kener", "SECRET_KEY", "x" * 31),
        ("kener", "SMTP_PORT", "port"),
        ("kener", "SMTP_PASS", "p$word"),
        ("observability", "INFLUXDB_PASSWORD", "short"),
        ("observability", "DISCORD_WEBHOOK", "https://example.com/hook/1/abc"),
        ("observability", "GITHUB_APP_PRIVATE_KEY", "MIIEfake"),
        ("matherlynet", "SMTP_URL", "smtp.example.com"),
        ("matherlynet", "MAIL_FROM", "a$b@example.com"),
        ("cliproxyapi", "OHMYCPA_MASTER_KEY", "x" * 64),
    ],
)
def test_malformed_value_is_reported(item, label, value):
    assert f"{item}/{label}: pattern" in check({item: [{"label": label, "value": value}]}, {})


def test_report_never_contains_a_value():
    f = {"label": "ACCESS_KEY", "value": "bad key$"}
    assert "bad key$" not in "\n".join(check({"etcd-backup": [f]}, CFG))


def test_each_env_key_is_a_field():
    config = {"ai_workspace_enabled": True, "ai_workspace": {"env_keys": ["VENDOR_KEY"]}}
    assert "ai-workspace-env/VENDOR_KEY: missing" in check({}, config)
    found = {"ai-workspace-env": [{"label": "VENDOR_KEY", "value": "abc"}]}
    assert not [p for p in check(found, config) if p.startswith("ai-workspace-env/")]


@pytest.mark.parametrize(
    ("item", "label", "other_item", "other_label"),
    [
        ("etcd-backup", "ACCESS_KEY", "postgres-backup", "ACCESS_KEY_ID"),
        ("volume-backup", "ACCESS_KEY", "postgres-backup", "ACCESS_KEY_ID"),
        ("volume-backup", "ACCESS_KEY", "etcd-backup", "ACCESS_KEY"),
        ("volume-backup", "BUCKET", "etcd-backup", "BUCKET"),
        ("langfuse", "RUSTFS_ACCESS_KEY", "rustfs", "ACCESS_KEY"),
        ("langfuse", "RUSTFS_ACCESS_KEY", "ai-kb", "RUSTFS_ACCESS_KEY"),
        ("itsaplan", "RUSTFS_ACCESS_KEY", "langfuse", "RUSTFS_ACCESS_KEY"),
    ],
)
def test_separate_accounts_must_not_share_a_value(item, label, other_item, other_label):
    found = {
        item: [{"label": label, "value": "samevalue1234567"}],
        other_item: [{"label": other_label, "value": "samevalue1234567"}],
    }
    assert f"{item}/{label}: same as {other_item}/{other_label}" in check(found, {})


def test_backup_bucket_must_not_be_the_database_bucket():
    found = {"volume-backup": [{"label": "BUCKET", "value": "db"}]}
    config = {"postgres": {"backup": {"bucket": "db"}}}
    assert "volume-backup/BUCKET: same as postgres.backup.bucket" in check(found, config)


def test_ai_workspace_admin_must_be_admitted():
    found = {
        "ai-workspace": [
            {"label": "ALLOWED_EMAILS", "value": "@example.com"},
            {"label": "ADMIN_EMAILS", "value": "boss@other.org"},
        ]
    }
    problem = "ai-workspace/ADMIN_EMAILS: an admin is not admitted by ALLOWED_EMAILS"
    problems = check(found, {"ai_workspace": {"admins": True, "allowlist": True}})
    assert problem in problems
    assert "boss@other.org" not in "\n".join(problems)
    # A list whose flag is off is not rendered, so a stale field is no problem.
    assert problem not in check(found, {"ai_workspace": {"admins": True, "allowlist": False}})
    assert problem not in check(found, {"ai_workspace": {"admins": False, "allowlist": True}})


def test_career_ops_needs_the_credential_its_mode_names():
    proxy = {"career_ops_enabled": True, "career_ops": {"claude_credential": "proxy"}}
    oauth = {"career_ops_enabled": True, "career_ops": {"claude_credential": "oauth"}}
    assert "career-ops/ANTHROPIC_AUTH_TOKEN: missing" in check({}, proxy)
    assert "career-ops/CLAUDE_OAUTH_TOKEN: missing" not in check({}, proxy)
    assert "career-ops/CLAUDE_OAUTH_TOKEN: missing" in check({}, oauth)
    assert "career-ops/ANTHROPIC_AUTH_TOKEN: missing" not in check({}, oauth)
