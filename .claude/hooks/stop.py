# /// script
# requires-python = ">=3.12"
# ///
"""Stop hook: block the turn while template changes fail the template checks.

Renders every valid fixture in a scratch copy of the working tree, so it never
needs the real cluster.toml or secrets, then runs the checks CI runs. Exits 2
with the failure so Claude fixes it before finishing; exits 0 when nothing
relevant changed, the last passing state is unchanged, or the checks pass.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))
WATCHED = [
    "template",
    "cluster.sample.toml",
    "cluster.schema.json",
    "makejinja.toml",
    "pyproject.toml",
    "uv.lock",
    ".github/template-tests",
]
FIXTURES = ROOT / ".github/template-tests/valid"
# Full validation on the fixture that enables the most features; the rest only
# render and format-check, which is where undefined variables in conditional
# branches show up.
FULL_FIXTURE = "public"
STAMP_DIR = Path(tempfile.gettempdir()) / f"home-cluster-stop-{hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]}"
PASS_STAMP = STAMP_DIR / "pass"
FAIL_STAMP = STAMP_DIR / "fail"
RENDERED = ["bootstrap", "kubernetes", "talos"]
NETWORK_ERROR = re.compile(r"no such host|dial tcp|connection refused|i/o timeout|could not (fetch|download)|TLS handshake", re.I)


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def tail(result: subprocess.CompletedProcess, lines: int = 20) -> str:
    return "\n".join((result.stdout + result.stderr).strip().splitlines()[-lines:])


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def state_hash() -> str | None:
    if not git("status", "--porcelain", "--", *WATCHED).strip():
        return None
    digest = hashlib.sha256(git("diff", "HEAD", "--", *WATCHED).encode())
    for path in git("ls-files", "--others", "--exclude-standard", "--", *WATCHED).splitlines():
        digest.update(path.encode() + (ROOT / path).read_bytes())
    return digest.hexdigest()


def tool_env(scratch: Path) -> dict[str, str]:
    mise = json.loads(subprocess.run(["mise", "env", "-C", str(ROOT), "--json"], capture_output=True, text=True, check=True).stdout)
    return {
        **os.environ,
        **mise,
        "PYTHONDONTWRITEBYTECODE": "1",
        # Reuse the repo's venv instead of building one per scratch copy.
        "UV_PROJECT_ENVIRONMENT": str(ROOT / ".venv"),
        "SOPS_AGE_KEY_FILE": str(scratch / "age.key"),
        "SOPS_CONFIG": str(scratch / ".sops.yaml"),
        "KUBECONFIG": str(scratch / "kubeconfig"),
    }


def make_scratch() -> Path:
    scratch = Path(tempfile.mkdtemp(prefix="home-cluster-check-"))
    for path in git("ls-files", "--cached", "--others", "--exclude-standard").splitlines():
        src = ROOT / path
        if src.is_file():
            (scratch / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, scratch / path)
    return scratch


def seed_secrets(scratch: Path, env: dict[str, str]) -> None:
    run(["age-keygen", "-o", "age.key"], scratch, env)
    run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", "deploy.key"], scratch, env)
    (scratch / "flux-webhook-token.txt").write_text("0" * 32 + "\n")
    (scratch / "cloudflare-tunnel.json").write_text('{"AccountTag":"fake","TunnelSecret":"fake","TunnelID":"fake"}')


def check(scratch: Path, env: dict[str, str]) -> list[str]:
    # (check, output) -> fixtures, so one broken template reports once, not per fixture.
    failures: dict[tuple[str, str], list[str]] = {}
    changed = git("status", "--porcelain", "--", "template/scripts", "pyproject.toml", "uv.lock")
    if changed.strip():
        r = run(["uv", "run", "--quiet", "--locked", "pytest", "template/scripts/test_validate.py", "-q"], scratch, env)
        if r.returncode:
            failures[("pytest template/scripts/test_validate.py", tail(r))] = []

    for fixture in sorted(FIXTURES.glob("*.toml"), key=lambda f: f.stem != FULL_FIXTURE):
        for rendered in RENDERED:
            shutil.rmtree(scratch / rendered, ignore_errors=True)
        (scratch / ".sops.yaml").unlink(missing_ok=True)
        shutil.copy2(fixture, scratch / "cluster.toml")

        r = run(["uv", "run", "--quiet", "--locked", "--no-dev", "makejinja"], scratch, env)
        if r.returncode:
            failures.setdefault(("render", tail(r, 5)), []).append(fixture.name)
            continue
        r = run(["oxfmt", "--check", "./.sops.yaml", "./bootstrap", "./kubernetes", "./talos"], scratch, env)
        if r.returncode:
            failures.setdefault(("oxfmt --check on rendered output", tail(r)), []).append(fixture.name)
        if fixture.stem != FULL_FIXTURE:
            continue

        r = run(["bash", "template/resources/kubeconform.sh", "kubernetes"], scratch, env)
        if r.returncode and not NETWORK_ERROR.search(r.stdout + r.stderr):
            failures.setdefault(("kubeconform", tail(r)), []).append(fixture.name)
        r = run(["topf", "render", "--confirm=false", "--output", tempfile.mkdtemp()], scratch / "talos", env)
        if r.returncode:
            failures.setdefault(("topf render", tail(r, 5)), []).append(fixture.name)
    return [
        f"{name}{f' ({", ".join(fixtures)})' if fixtures else ''}\n{output}"
        for (name, output), fixtures in failures.items()
    ]


def main() -> int:
    payload = json.load(sys.stdin)
    if not (ROOT / "template").is_dir():
        return 0
    current = state_hash()
    if current is None or (PASS_STAMP.is_file() and PASS_STAMP.read_text() == current):
        return 0
    # Already blocked once and nothing changed since: let the turn end rather
    # than loop on a failure Claude has not touched.
    if payload.get("stop_hook_active") and FAIL_STAMP.is_file() and FAIL_STAMP.read_text() == current:
        return 0
    STAMP_DIR.mkdir(exist_ok=True)

    scratch = make_scratch()
    try:
        env = tool_env(scratch)
        seed_secrets(scratch, env)
        failures = check(scratch, env)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print("Template checks failed (fixtures in .github/template-tests/valid). Fix these before finishing:\n", file=sys.stderr)
        print("\n\n".join(failures), file=sys.stderr)
        FAIL_STAMP.write_text(current)
        return 2
    PASS_STAMP.write_text(current)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        # Fail open: a broken hook must not trap the session.
        print(f"stop hook skipped: {error!r}", file=sys.stderr)
        sys.exit(0)
