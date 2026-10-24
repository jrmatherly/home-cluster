# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""List every chart and every image pinned in the templates, with the newest stable tag.

Usage: inventory.py [app-name ...]
Exits 1 when a lookup fails or finds no stable tag, so a "?" in the table is never silent.
A chart from a classic HelmRepository is a `helmrepo` row, read from the repository's index.yaml.
A tag pinned with a digest is also checked against the registry: when the tag's digest moved, the
bump reads `digest`, because Renovate opens a PR for that and the tag alone would show `none`.
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
# suffix. The suffix covers tags such as 2.9.1-alpine and
# v4.11.0-gpu-nvidia-cuda-12-llama-cpp; a pre-release such as 1.4.0-rc1 reads
# as a suffix too, which is what keeps it from being offered.
# The patch number is optional, because some images publish only 1.38 (busybox) or
# 18.6-standard-trixie (CloudNativePG), and a fourth part is allowed for the Servarr
# builds (4.0.20.3012) and CalVer releases (v2026.10.12.2); missing parts read as 0.
# The prefix holds no digit, or it would swallow the major of a four-part tag. A suffix
# may open with a number and a word (0.26.2-18-trixie, ParadeDB's extension image: the
# Postgres major and the Debian release), but a bare number (1.2.3-4) is a build, not a
# variant.
STABLE = re.compile(
    r"^(\D*?v?)(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?(-(?:\d+-)?[a-z][a-z0-9.-]*|-[0-9a-f]{7,})?$"
)
PLAIN = ("", "v")
# A suffix that is only a commit hash (SearXNG's 2026.10.23-68647d080) names a build of
# that day, not a variant: every such tag shares this style, so the newest day wins.
BUILD = re.compile(r"^-[0-9a-f]{7,}$")
BUILD_STYLE = "-<build>"
# Docker Hub serves its registry API from a different host than its image names.
REGISTRY_HOSTS = {"docker.io": "registry-1.docker.io"}
MANIFEST_TYPES = (
    "application/vnd.oci.image.index.v1+json, "
    "application/vnd.docker.distribution.manifest.list.v2+json, "
    "application/vnd.oci.image.manifest.v1+json, "
    "application/vnd.docker.distribution.manifest.v2+json"
)
DIGEST = r'(?:@(sha256:[0-9a-f]+))?'


def pins() -> list[tuple[str, str, str, str, str, Path]]:
    """Return (app, kind, repository, current tag, pinned digest or "", file) for every pin.

    A `helmrepo` row's repository is `<HelmRepository url>#<chart name>`.
    """
    found = []
    for path in sorted(TEMPLATES.rglob("*.j2")):
        text = path.read_text()
        rel = path.relative_to(ROOT)
        if path.name == "ocirepository.yaml.j2":
            url = re.search(r"url: oci://(\S+)", text)
            tag = re.search(r"tag: (\S+)", text)
            if url and tag:
                found.append((path.parts[-3], "chart", url[1], tag[1], "", rel))
        elif path.name == "helmrelease.yaml.j2":
            for repo, tag, digest in re.findall(
                rf'repository: (\S+)\n\s+tag: "?([^\s@"]+){DIGEST}', text
            ):
                found.append((path.parts[-3], "image", repo, tag, digest, rel))
            # A chart from a classic HelmRepository (csi-driver-nfs, rustfs) is pinned in the
            # HelmRelease, with the repository URL in the sibling helmrepository.yaml.j2.
            chart = re.search(r"\n\s+chart: (\S+)\n\s+version: (\S+)", text)
            repo_file = path.with_name("helmrepository.yaml.j2")
            if chart and repo_file.exists():
                url = re.search(r"url: (\S+)", repo_file.read_text())
                if url:
                    found.append(
                        (path.parts[-3], "helmrepo", f"{url[1]}#{chart[1]}", chart[2], "", rel)
                    )
        if "helmfile" not in path.parts:
            # Single-line pins: image volumes under persistence, plain Deployments, CronJobs,
            # the Redis component, the Postgres ImageCatalog and a CNPG extension image
            # (`reference:`). Skipped: a `latest` tag (the docs image; Renovate moves its
            # digest) and the model images, whose tags are a quantization plus a revision and
            # are bumped by hand (apps.md, localai).
            app = path.parts[-3] if path.parts[-2] == "app" else path.parts[-2]
            for repo, tag, digest in re.findall(
                rf'\n\s+(?:image|reference): "?([^\s"@:]+(?:/[^\s"@:]+)+):([^\s@"]+){DIGEST}', text
            ):
                if tag != "latest" and not repo.startswith("ghcr.io/jrmatherly/models/"):
                    found.append((app, "image", repo, tag, digest, rel))
        if "helmfile" in path.parts:
            # A "# renovate:" comment may sit between the chart and its version.
            for name, repo, version in re.findall(
                r"name: (\S+)\n(?:.*\n){0,3}?\s+chart: oci://(\S+)\n(?:\s*#.*\n)*\s+version: (\S+)",
                text,
            ):
                found.append((name, "chart", repo, version, "", rel))
    return found


def fetch(url: str, token: str | None = None, accept: str | None = None, method: str = "GET"):
    """Return (body bytes, headers) for one request."""
    # charts.rustfs.com answers Python's default agent with 403.
    request = urllib.request.Request(url, method=method, headers={"User-Agent": "curl/8"})
    if accept:
        request.add_header("Accept", accept)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read(), response.headers


TOKENS: dict[str, str] = {}


def registry(repository: str, path: str, accept: str | None = None, method: str = "GET"):
    """Fetch a v2 registry path (or a full URL the registry handed back), taking the bearer
    token the registry asks for on 401."""
    base, name = registry_base(repository)
    url = path if path.startswith("https://") else base + path
    while True:
        try:
            return fetch(url, TOKENS.get(repository), accept, method)
        except urllib.error.HTTPError as error:
            challenge = error.headers.get("WWW-Authenticate", "")
            if error.code != 401 or repository in TOKENS or "Bearer" not in challenge:
                raise
            fields = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
            query = f"service={fields.get('service', '')}&scope=repository:{name}:pull"
            body, _ = fetch(f"{fields['realm']}?{query}")
            token_body = json.loads(body)
            TOKENS[repository] = token_body.get("token") or token_body["access_token"]


def tags(repository: str) -> list[str]:
    path = "tags/list?n=1000"
    found: list[str] = []
    while path:
        body, headers = registry(repository, path)
        found += json.loads(body).get("tags") or []
        next_page = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", ""))
        # The next link is relative to the registry root, so it becomes a full URL.
        path = urllib.parse.urljoin(registry_base(repository)[0], next_page[1]) if next_page else ""
    return found


def registry_base(repository: str) -> tuple[str, str]:
    """Return the v2 API base URL and the repository name the token scope uses."""
    host, _, name = repository.partition("/")
    if "." not in host and ":" not in host:
        # A Docker Hub short name such as localai/localai: the first segment is a user.
        host, name = "docker.io", repository
    return f"https://{REGISTRY_HOSTS.get(host, host)}/v2/{name}/", name


def digest(repository: str, tag: str) -> str:
    """Return the digest the registry serves for a tag today."""
    _, headers = registry(repository, f"manifests/{tag}", MANIFEST_TYPES, "HEAD")
    return headers.get("Docker-Content-Digest", "")


def helmrepo_versions(repository: str) -> list[str]:
    """Return every version of a chart in a classic HelmRepository's index.yaml."""
    url, _, chart = repository.partition("#")
    body, _ = fetch(f"{url.rstrip('/')}/index.yaml")
    lines = body.decode().splitlines()
    versions: list[str] = []
    inside = False
    for line in lines:
        if line == f"  {chart}:":
            inside = True
            continue
        # The next chart name sits at the same indent; a list item or field is deeper.
        if inside and (re.match(r"^  [^ -]", line) or re.match(r"^\S", line)):
            break
        if inside and (found := re.match(r"^\s+version: (\S+)$", line)):
            versions.append(found[1])
    return versions


def parse(tag: str) -> tuple[tuple[str, str], tuple[int, ...]] | None:
    """Return ((prefix, suffix), version) for a stable tag, or None.

    >>> parse("v1.21.2")
    (('v', ''), (1, 21, 2, 0))
    >>> parse("v4.11.0-gpu-nvidia-cuda-12-llama-cpp")
    (('v', '-gpu-nvidia-cuda-12-llama-cpp'), (4, 11, 0, 0))
    >>> parse("2.9.1-alpine")
    (('', '-alpine'), (2, 9, 1, 0))
    >>> parse("18.6-standard-trixie")
    (('', '-standard-trixie'), (18, 6, 0, 0))
    >>> parse("0.26.2-18-trixie")
    (('', '-18-trixie'), (0, 26, 2, 0))
    >>> parse("4.0.20.3012"), parse("v2026.10.12.2")
    ((('', ''), (4, 0, 20, 3012)), (('v', ''), (2026, 10, 12, 2)))
    >>> parse("latest"), parse("3"), parse("1.2.3-4"), parse("1.2.3.4.5")
    (None, None, None, None)
    >>> parse("2026.10.23-68647d080")
    (('', '-<build>'), (2026, 10, 23, 0))
    """
    match = STABLE.match(tag)
    if not match:
        return None
    suffix = match[6] or ""
    if BUILD.match(suffix):
        suffix = BUILD_STYLE
    return (match[1], suffix), tuple(int(part or 0) for part in match.groups()[1:5])


def version(tag: str) -> tuple[int, ...] | None:
    parsed = parse(tag)
    return parsed[1] if parsed else None


def latest_stable(kind: str, repository: str, current: str) -> str:
    prefix, suffix = parsed[0] if (parsed := parse(current)) else ("", "")
    candidates = helmrepo_versions(repository) if kind == "helmrepo" else tags(repository)
    found = [(parsed, tag) for tag in candidates if (parsed := parse(tag))]
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
    >>> newest(found, "cuda-v", "")
    '?'
    >>> bump("1.38", newest([(parse(tag), tag) for tag in ("1.38", "1.38.0")], "", ""))
    'none'
    >>> servarr = [(parse(tag), tag) for tag in ("4.0.20.3012", "4.1.0.1", "5.0.0.7")]
    >>> newest(servarr, "", ""), bump("4.0.20.3012", "4.1.0.1")
    ('5.0.0.7', 'minor')
    >>> newest([(parse(tag), tag) for tag in ("v2026.10.12.2", "v2027.1.2.1")], "v", "")
    'v2027.1.2.1'
    >>> builds = [(parse(tag), tag) for tag in ("2026.10.15-b00212a83", "2026.10.23-68647d080")]
    >>> newest(builds, "", BUILD_STYLE)
    '2026.10.23-68647d080'
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
    for app, kind, repository, current, pinned, path in pins():
        if wanted and app not in wanted:
            continue
        try:
            latest = latest_stable(kind, repository, current)
            if latest == "?":
                print(f"{app}: no stable tag found in {repository}", file=sys.stderr)
                failed = True
            change = bump(current, latest)
            if change == "none" and pinned and digest(repository, current) != pinned:
                change = "digest"
        # OSError covers URLError, timeouts and a connection the proxy drops.
        except (OSError, KeyError, json.JSONDecodeError) as error:
            print(f"{app}: lookup failed for {repository}: {error}", file=sys.stderr)
            latest, change, failed = "?", "unknown", True
        rows.append((app, kind, current, latest, change, str(path)))
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())
    missing = wanted - {row[0] for row in rows}
    if missing:
        print(f"no pin found for: {', '.join(sorted(missing))}", file=sys.stderr)
    return 1 if failed or missing else 0


if __name__ == "__main__":
    sys.exit(main())
