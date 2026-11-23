"""Unit tests for the 1Password secret map, the seeding templates and secrets-check.

Run from the repo root:
    uv run --locked pytest template/scripts/test_secret_map.py -q
"""

import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import op_seed
from pydantic import BaseModel
from secret_map import ENTRIES, GATES, MOVING_PATHS, items, lookup
from secrets_check import check
from validate import Config, load

REPO_ROOT = Path(__file__).parents[2]
FULL = REPO_ROOT / ".github/template-tests/valid/public.toml"
CFG = {"kener_enabled": True, "etcd_backup_enabled": True}
# Stand-ins for the two secret files beside the config.
FILES = {
    f"{op_seed.TUNNEL_FILE}#AccountTag": "account",
    f"{op_seed.TUNNEL_FILE}#TunnelSecret": "secret",
    op_seed.WEBHOOK_FILE: "token",
}


def seeded(config: dict) -> dict[str, list[dict]]:
    templates = op_seed.build_templates(config, FILES)
    return {title: template["fields"] for title, template in templates.items()}


def dotted_paths(model: type[BaseModel], prefix: str = "") -> set[str]:
    paths = set()
    for name, field in model.model_fields.items():
        nested = field.annotation
        if isinstance(nested, type) and issubclass(nested, BaseModel):
            paths |= dotted_paths(nested, f"{prefix}{name}.")
        else:
            paths.add(prefix + name)
    return paths


def test_moving_paths_exist_in_the_model():
    assert MOVING_PATHS <= dotted_paths(Config)


def test_every_requirement_is_a_gate_or_a_config_path():
    config = load(str(FULL))
    unknown = [
        e.requires
        for e in ENTRIES
        if e.requires not in GATES and lookup(config, e.requires) is None
    ]
    assert not unknown


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


def test_bad_label_is_reported():
    f = {"label": "SECRET_KEY", "value": "x" * 32}
    assert "kener/SECRET_KEY: duplicate label" in check({"kener": [f, f]}, CFG)
    g = {"label": "SECRET KEY", "value": "x" * 32}
    assert "kener/SECRET KEY: label has a space" in check({"kener": [g]}, CFG)


def test_pattern_rules_are_enforced():
    f = {"label": "ACCESS_KEY", "value": "bad key$"}
    assert "etcd-backup/ACCESS_KEY: pattern" in check({"etcd-backup": [f]}, CFG)


def test_report_never_contains_a_value():
    f = {"label": "ACCESS_KEY", "value": "bad key$"}
    assert "bad key$" not in "\n".join(check({"etcd-backup": [f]}, CFG))


def test_seeded_full_fixture_passes_the_check():
    """What op_seed writes for a config is what secrets-check accepts for it."""
    config = load(str(FULL))
    assert check(seeded(config), config) == []


def test_seed_takes_each_value_from_its_path():
    raw = tomllib.loads(FULL.read_text())
    assert seeded(load(str(FULL)))["dns"] == [
        {"id": "TOKEN", "type": "CONCEALED", "label": "TOKEN", "value": raw["dns"]["token"]}
    ]


def test_seed_skips_what_is_unset():
    config = load(str(REPO_ROOT / ".github/template-tests/valid/single-node.toml"))
    assert set(seeded(config)) == {"cluster", "cloudflare-tunnel", "flux"}


def test_kener_smtp_url_is_split():
    config = load(str(FULL))
    config["kener_smtp"] = {
        "host": "smtp.example.com",
        "port": "465",
        "user": "a",
        "password": "b",
        "secure": "1",
    }
    fields = {f["label"]: f["value"] for f in seeded(config)["kener"]}
    assert (fields["SMTP_HOST"], fields["SMTP_PORT"], fields["SMTP_SECURE"]) == (
        "smtp.example.com",
        "465",
        "1",
    )
    assert "SMTP_URL" not in fields


def test_lists_are_stored_comma_joined():
    config = load(str(FULL))
    config["ai_workspace"]["allowed_emails"] = ["a@example.com", "@example.org"]
    fields = {f["label"]: f["value"] for f in seeded(config)["ai-workspace"]}
    assert fields["ALLOWED_EMAILS"] == "a@example.com,@example.org"


def test_each_env_key_becomes_a_field():
    config = load(str(FULL))
    config["ai_workspace"]["env"] = {"VENDOR_KEY": "abc"}
    assert seeded(config)["ai-workspace-env"] == [
        {"id": "VENDOR_KEY", "type": "CONCEALED", "label": "VENDOR_KEY", "value": "abc"}
    ]
    config["ai_workspace_enabled"] = True
    assert "ai-workspace-env/VENDOR_KEY: missing" in check({}, config)


def test_backup_pairs_must_differ():
    found = {
        "etcd-backup": [{"label": "ACCESS_KEY", "value": "samekey"}],
        "postgres-backup": [{"label": "ACCESS_KEY_ID", "value": "samekey"}],
    }
    assert "etcd-backup/ACCESS_KEY: same as postgres-backup/ACCESS_KEY_ID" in check(found, {})


def test_backup_bucket_must_not_be_the_database_bucket():
    found = {"volume-backup": [{"label": "BUCKET", "value": "db"}]}
    config = {"postgres": {"backup": {"bucket": "db"}}}
    assert "volume-backup/BUCKET: same as postgres.backup.bucket" in check(found, config)


def test_rustfs_access_keys_must_be_unique():
    found = {
        "rustfs": [{"label": "ACCESS_KEY", "value": "A" * 16}],
        "langfuse": [{"label": "RUSTFS_ACCESS_KEY", "value": "A" * 16}],
    }
    assert "langfuse/RUSTFS_ACCESS_KEY: same as rustfs/ACCESS_KEY" in check(found, {})


def test_ai_workspace_admin_must_be_admitted():
    found = {
        "ai-workspace": [
            {"label": "ALLOWED_EMAILS", "value": "@example.com"},
            {"label": "ADMIN_EMAILS", "value": "boss@other.org"},
        ]
    }
    problems = check(found, {})
    assert "ai-workspace/ADMIN_EMAILS: an admin is not admitted by ALLOWED_EMAILS" in problems
    assert "boss@other.org" not in "\n".join(problems)


def test_career_ops_needs_the_credential_its_mode_names():
    proxy = {"career_ops_enabled": True, "career_ops": {"anthropic_base_url": "http://x"}}
    oauth = {"career_ops_enabled": True, "career_ops": {"anthropic_base_url": ""}}
    assert "career-ops/ANTHROPIC_AUTH_TOKEN: missing" in check({}, proxy)
    assert "career-ops/CLAUDE_OAUTH_TOKEN: missing" not in check({}, proxy)
    assert "career-ops/CLAUDE_OAUTH_TOKEN: missing" in check({}, oauth)
