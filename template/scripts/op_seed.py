"""Create the 1Password items of the secret map from cluster.toml.

Prints item titles only. Each item goes to `op item create` as a JSON template
on stdin, so no value appears in a process argument. An item whose title exists
is skipped: `op item create` never updates, it would add a second item of the
same title and make every reference to it ambiguous.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from secret_map import EACH_KEY, Entry, items, lookup
from secrets_check import check
from validate import ConfigError, load

TUNNEL_FILE = "cloudflare-tunnel.json"
WEBHOOK_FILE = "flux-webhook-token.txt"
# The computed field that holds the parts of a value stored split.
_SPLIT = {"kener.smtp_url": "kener_smtp"}


def _values(entry: Entry, config: dict[str, Any], files: dict[str, str]) -> dict[str, str]:
    """The label and value of each field an entry yields; none when the value is unset."""
    value: Any
    if entry.source.startswith("file:"):
        value = files.get(entry.source.removeprefix("file:"))
    else:
        path, _, part = entry.source.removeprefix("copy:").partition("#")
        value = lookup(config, f"{_SPLIT[path]}.{part}") if part else lookup(config, path)
    if entry.field == EACH_KEY:
        return dict(value or {})
    if isinstance(value, list):
        value = ",".join(value)
    return {entry.field: value} if value else {}


def build_templates(
    config: dict[str, Any], files: dict[str, str] | None = None
) -> dict[str, dict[str, Any]]:
    """One `op item create` JSON template per item that has a value to hold."""
    templates = {}
    for title, entries in items().items():
        fields = [
            {"id": label, "type": "CONCEALED", "label": label, "value": value}
            for entry in entries
            for label, value in _values(entry, config, files or {}).items()
        ]
        if fields:
            templates[title] = {"title": title, "category": "API_CREDENTIAL", "fields": fields}
    return templates


def read_files(root: Path) -> dict[str, str]:
    """The secrets kept in files beside cluster.toml, keyed as the map's file sources are."""
    files = {}
    tunnel = root / TUNNEL_FILE
    if tunnel.is_file():
        data = json.loads(tunnel.read_text())
        files |= {f"{TUNNEL_FILE}#{key}": data[key] for key in ("AccountTag", "TunnelSecret")}
    webhook = root / WEBHOOK_FILE
    if webhook.is_file():
        files[WEBHOOK_FILE] = webhook.read_text().strip()
    return files


def _plan(templates: dict[str, dict[str, Any]], config: dict[str, Any]) -> int:
    """Print what a seed would create, labels only, and check it without calling 1Password."""
    fields = {title: template["fields"] for title, template in templates.items()}
    for title, found in fields.items():
        print(f"{title}: {', '.join(field['label'] for field in found)}")
    problems = check(fields, config)
    for problem in problems:
        print(problem)
    print(f"{len(fields)} items, {len(problems)} problems")
    return 1 if problems else 0


def main(config_file: str = "cluster.toml", flag: str = "") -> int:
    try:
        config = load(config_file)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    vault = config["onepassword"]["vault"]
    if not vault:
        print("[onepassword].vault is not set", file=sys.stderr)
        return 1
    templates = build_templates(config, read_files(Path(config_file).resolve().parent))
    if flag == "--dry-run":
        return _plan(templates, config)
    listing = subprocess.run(
        ["op", "item", "list", "--vault", vault, "--format", "json"],
        capture_output=True,
        check=False,
        text=True,
    )
    if listing.returncode:
        print(
            f"1Password vault {vault!r} is unreachable: {listing.stderr.strip()}", file=sys.stderr
        )
        return 1
    existing = {item["title"] for item in json.loads(listing.stdout)}
    for title, template in templates.items():
        if title in existing:
            print(f"{title}: exists, skipped")
            continue
        created = subprocess.run(
            ["op", "item", "create", "--vault", vault, "-"],
            input=json.dumps(template),
            capture_output=True,
            check=False,
            text=True,
        )
        if created.returncode:
            print(f"{title}: failed: {created.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"{title}: created")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
