# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""List every OCI chart and every image pinned in the templates, with the newest stable tag.

Usage: inventory.py [app-name ...]
Exits 1 when a lookup fails or finds no stable tag, so a "?" in the table is never silent.
"""

import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    ).stdout.strip()
)
TEMPLATES = ROOT / "template/config"
# An optional variant prefix, then 1.2.3 or v1.2.3, then an optional variant
# suffix. The prefix covers image tags such as server-cuda-v0.5.0, and the
# suffix covers ones such as 2.9.1-alpine.
STABLE = re.compile(r"^(.*?v?)(\d+)\.(\d+)\.(\d+)(-[a-z][a-z0-9.]*)?$")
PLAIN = ("", "v")
# Docker Hub serves its registry API from a different host than its image names.
REGISTRY_HOSTS = {"docker.io": "registry-1.docker.io"}


def pins() -> list[tuple[str, str, str, str, Path]]:
    """Return (app, kind, repository, current tag, file) for every pin."""
    found = []
    for path in sorted(TEMPLATES.rglob("*.j2")):
        text = path.read_text()
        rel = path.relative_to(ROOT)
        if path.name == "ocirepository.yaml.j2":
            url = re.search(r"url: oci://(\S+)", text)
            tag = re.search(r"tag: (\S+)", text)
            if url and tag:
                found.append((path.parts[-3], "chart", url[1], tag[1], rel))
        elif path.name == "helmrelease.yaml.j2":
            # A tag may carry a digest (1.2.3@sha256:...); the table shows the tag alone.
            for repo, tag in re.findall(r"repository: (\S+)\n\s+tag: ([^\s@]+)", text):
                found.append((path.parts[-3], "image", repo, tag, rel))
        elif "helmfile" in path.parts:
            # A "# renovate:" comment may sit between the chart and its version.
            for name, repo, version in re.findall(
                r"name: (\S+)\n(?:.*\n){0,3}?\s+chart: oci://(\S+)\n(?:\s*#.*\n)*\s+version: (\S+)",
                text,
            ):
                found.append((name, "chart", repo, version, rel))
    return found


def get(url: str, token: str | None = None) -> tuple[dict, str]:
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response), response.headers.get("Link", "")


def tags(repository: str) -> list[str]:
    host, _, name = repository.partition("/")
    host = REGISTRY_HOSTS.get(host, host)
    url = f"https://{host}/v2/{name}/tags/list?n=1000"
    token = None
    found: list[str] = []
    while url:
        try:
            body, link = get(url, token)
        except urllib.error.HTTPError as error:
            challenge = error.headers.get("WWW-Authenticate", "")
            if error.code != 401 or token or "Bearer" not in challenge:
                raise
            fields = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
            query = f"service={fields.get('service', '')}&scope=repository:{name}:pull"
            token_body, _ = get(f"{fields['realm']}?{query}")
            token = token_body.get("token") or token_body["access_token"]
            continue
        found += body.get("tags") or []
        next_page = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = urllib.parse.urljoin(url, next_page[1]) if next_page else ""
    return found


def parse(tag: str) -> tuple[tuple[str, str], tuple[int, ...]] | None:
    """Return ((prefix, suffix), version) for a stable tag, or None.

    >>> parse("v1.21.2")
    (('v', ''), (1, 21, 2))
    >>> parse("server-cuda-v0.5.0")
    (('server-cuda-v', ''), (0, 5, 0))
    >>> parse("2.9.1-alpine")
    (('', '-alpine'), (2, 9, 1))
    >>> parse("latest"), parse("3.7"), parse("1.2.3-4")
    (None, None, None)
    """
    match = STABLE.match(tag)
    if not match:
        return None
    return (match[1], match[5] or ""), tuple(int(part) for part in match.groups()[1:4])


def version(tag: str) -> tuple[int, ...] | None:
    parsed = parse(tag)
    return parsed[1] if parsed else None


def latest_stable(repository: str, current: str) -> str:
    prefix, suffix = parsed[0] if (parsed := parse(current)) else ("", "")
    found = [(parsed, tag) for tag in tags(repository) if (parsed := parse(tag))]
    return newest(found, prefix, suffix)


def newest(found: list, prefix: str, suffix: str) -> str:
    """Return the highest tag in found that has the pinned prefix and suffix, or "?".

    >>> found = [(parse(tag), tag) for tag in ("2.9.1", "2.9.1-alpine", "2.9.0-alpine", "3.5.0-core")]
    >>> newest(found, "", "-alpine")
    '2.9.1-alpine'
    >>> newest([(parse(tag), tag) for tag in ("v1.3.0", "1.2.0", "1.4.0-rc1")], "", "")
    '1.2.0'
    >>> newest([(parse("v1.3.0"), "v1.3.0")], "", "")
    'v1.3.0'
    >>> newest(found, "server-cuda-v", "")
    '?'
    """
    same_style = [(number, tag) for (style, number), tag in found if style == (prefix, suffix)]
    # Some repositories publish both 1.2.3 and v1.2.3; keep the style already pinned.
    # A variant never falls back, because another variant is a different image, and
    # a pre-release such as 1.4.0-rc1 reads as a variant, so it is never offered.
    if not same_style and prefix in PLAIN:
        same_style = [
            (number, tag)
            for (style, number), tag in found
            if style[0] in PLAIN and style[1] == suffix
        ]
    return max(same_style)[1] if same_style else "?"


def bump(current: str, latest: str) -> str:
    old, new = version(current), version(latest)
    if old is None or new is None:
        return "unknown"
    if new <= old:
        return "none"
    return "major" if new[0] > old[0] else "minor" if new[1] > old[1] else "patch"


def main() -> int:
    wanted = set(sys.argv[1:])
    rows = [("APP", "KIND", "CURRENT", "LATEST", "BUMP", "FILE")]
    failed = False
    for app, kind, repository, current, path in pins():
        if wanted and app not in wanted:
            continue
        try:
            latest = latest_stable(repository, current)
            if latest == "?":
                print(f"{app}: no stable tag found in {repository}", file=sys.stderr)
                failed = True
        # OSError covers URLError, timeouts and a connection the proxy drops.
        except (OSError, KeyError, json.JSONDecodeError) as error:
            print(f"{app}: lookup failed for {repository}: {error}", file=sys.stderr)
            latest, failed = "?", True
        rows.append((app, kind, current, latest, bump(current, latest), str(path)))
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())
    missing = wanted - {row[0] for row in rows}
    if missing:
        print(f"no pin found for: {', '.join(sorted(missing))}", file=sys.stderr)
    return 1 if failed or missing else 0


if __name__ == "__main__":
    sys.exit(main())
