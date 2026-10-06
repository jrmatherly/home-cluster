"""Check that a cluster.toml keeps its top-level tables in cluster.sample.toml's order.

The sample is the documented layout. A section added in the wrong place still
validates, so the schema cannot catch it; this does.
"""

import sys
import tomllib
from pathlib import Path


def misplaced(sample: list[str], config: list[str]) -> tuple[str, str] | None:
    """Return (found, expected) at the first table out of the sample's order, else None."""
    known = [key for key in config if key in sample]
    expected = sorted(known, key=sample.index)
    for found, want in zip(known, expected, strict=True):
        if found != want:
            return found, want
    return None


def main(sample_path: str, config_path: str) -> int:
    sample = list(tomllib.loads(Path(sample_path).read_text()))
    config = list(tomllib.loads(Path(config_path).read_text()))
    hit = misplaced(sample, config)
    if hit is None:
        return 0
    found, want = hit
    print(
        f"{config_path}: [{found}] is out of order, the sample has [{want}] there; "
        f"keep the sections in {sample_path}'s order",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
