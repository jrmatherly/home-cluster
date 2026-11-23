"""Check the 1Password items against the secret map.

Reports each problem as `<item>/<field>: <problem>` and never prints a value.
It holds the rules validate.py applied to a secret while the secret was in
cluster.toml: required fields, formats, and values that must differ.
"""

import json
import re
import subprocess
import sys
from typing import Any

from secret_map import EACH_KEY, ENTRIES, Entry, items, lookup, required
from validate import ConfigError, _admitted, load

type Key = tuple[str, str]

# Pairs that must not hold the same value, later one first. A backup key that
# also opens a wider bucket would put that bucket's contents inside the backup.
_DISTINCT: list[tuple[Key, Key]] = [
    (("etcd-backup", "ACCESS_KEY"), ("postgres-backup", "ACCESS_KEY_ID")),
    (("volume-backup", "ACCESS_KEY"), ("postgres-backup", "ACCESS_KEY_ID")),
    (("volume-backup", "ACCESS_KEY"), ("etcd-backup", "ACCESS_KEY")),
    (("volume-backup", "BUCKET"), ("etcd-backup", "BUCKET")),
    # RustFS scopes each consumer's pair to its own bucket, so every access key is unique.
    (("ai-kb", "RUSTFS_ACCESS_KEY"), ("rustfs", "ACCESS_KEY")),
    (("langfuse", "RUSTFS_ACCESS_KEY"), ("rustfs", "ACCESS_KEY")),
    (("langfuse", "RUSTFS_ACCESS_KEY"), ("ai-kb", "RUSTFS_ACCESS_KEY")),
    (("itsaplan", "RUSTFS_ACCESS_KEY"), ("rustfs", "ACCESS_KEY")),
    (("itsaplan", "RUSTFS_ACCESS_KEY"), ("ai-kb", "RUSTFS_ACCESS_KEY")),
    (("itsaplan", "RUSTFS_ACCESS_KEY"), ("langfuse", "RUSTFS_ACCESS_KEY")),
]
_BACKUP_BUCKETS: list[Key] = [("etcd-backup", "BUCKET"), ("volume-backup", "BUCKET")]


def _labels(entry: Entry, config: dict[str, Any]) -> list[str]:
    if entry.field != EACH_KEY:
        return [entry.field]
    return sorted(lookup(config, entry.source) or {})


def check(found: dict[str, list[dict[str, Any]]], config: dict[str, Any]) -> list[str]:
    """found maps an item title to its fields as `op item get --format json` returns them."""
    problems: list[str] = []
    values: dict[Key, str] = {}
    for item, fields in found.items():
        labels = [field.get("label", "") for field in fields]
        # One such label fails ESO's read of the whole item.
        for label in dict.fromkeys(labels):
            if " " in label:
                problems.append(f"{item}/{label}: label has a space")
            if labels.count(label) > 1:
                problems.append(f"{item}/{label}: duplicate label")
        values |= {(item, f.get("label", "")): f["value"] for f in fields if f.get("value")}

    for entry in ENTRIES:
        needed = required(entry, config)
        for label in _labels(entry, config):
            value = values.get((entry.item, label))
            if value is None:
                if needed:
                    problems.append(f"{entry.item}/{label}: missing")
            elif entry.pattern and not re.fullmatch(entry.pattern, value):
                problems.append(f"{entry.item}/{label}: pattern")

    for (item, label), (other_item, other_label) in _DISTINCT:
        value = values.get((item, label))
        if value is not None and value == values.get((other_item, other_label)):
            problems.append(f"{item}/{label}: same as {other_item}/{other_label}")
    database_bucket = lookup(config, "postgres.backup.bucket")
    for item, label in _BACKUP_BUCKETS:
        if database_bucket and values.get((item, label)) == database_bucket:
            problems.append(f"{item}/{label}: same as postgres.backup.bucket")

    admins = values.get(("ai-workspace", "ADMIN_EMAILS"), "")
    rules = values.get(("ai-workspace", "ALLOWED_EMAILS"), "")
    if admins and not all(
        _admitted(a, rules.split(",") if rules else []) for a in admins.split(",")
    ):
        problems.append("ai-workspace/ADMIN_EMAILS: an admin is not admitted by ALLOWED_EMAILS")
    return problems


def _fetch(title: str, vault: str) -> list[dict[str, Any]]:
    """An item's fields, or none when the vault has no item of that title."""
    result = subprocess.run(
        ["op", "item", "get", title, "--vault", vault, "--format", "json"],
        capture_output=True,
        check=False,
        text=True,
    )
    return json.loads(result.stdout).get("fields", []) if result.returncode == 0 else []


def main(config_file: str = "cluster.toml") -> int:
    try:
        config = load(config_file)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    vault = config["onepassword"]["vault"]
    if not vault:
        print("[onepassword].vault is not set", file=sys.stderr)
        return 1
    # Without this, a signed-out CLI would report every field as missing.
    reachable = subprocess.run(
        ["op", "vault", "get", vault], capture_output=True, check=False, text=True
    )
    if reachable.returncode:
        print(
            f"1Password vault {vault!r} is unreachable: {reachable.stderr.strip()}", file=sys.stderr
        )
        return 1
    problems = check({title: _fetch(title, vault) for title in items()}, config)
    for problem in problems:
        print(problem)
    print(f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
