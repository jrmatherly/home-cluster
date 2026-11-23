import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not all(shutil.which(tool) for tool in ("just", "git", "gum")),
    reason="needs just, git and gum",
)


def doctor_sops(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["just", "template", "doctor-sops"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_doctor_refuses_a_tracked_sops_file(tmp_path: Path):
    shutil.copy(ROOT / "justfile", tmp_path / "justfile")
    (tmp_path / "template").mkdir()
    shutil.copy(ROOT / "template/mod.just", tmp_path / "template/mod.just")
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    assert doctor_sops(tmp_path).returncode == 0

    leftover = tmp_path / "bootstrap" / "leftover.sops.yaml"
    leftover.parent.mkdir()
    leftover.write_text("kind: Secret\n")
    subprocess.run(["git", "add", "bootstrap"], cwd=tmp_path, check=True)

    result = doctor_sops(tmp_path)
    assert result.returncode == 1
    assert "bootstrap/leftover.sops.yaml" in result.stderr
