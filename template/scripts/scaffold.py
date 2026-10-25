"""Copy a section's block from cluster.sample.toml into cluster.toml, in the sample's position.

Prints line numbers only, never the config's contents. The block lands after the
end of the section that precedes it in the sample, so it never lands inside the
banner comment that sits above the next header.
"""

import re
import sys
import tomllib
from pathlib import Path

HEADER = re.compile(r"^\[\[?([A-Za-z0-9_.-]+)\]\]?\s*$")
BANNER = re.compile(r"^# =+\s*$")


def _header_lines(lines: list[str]) -> dict[str, int]:
    return {m.group(1): i for i, line in enumerate(lines) if (m := HEADER.match(line))}


def _block(lines: list[str], start: int) -> tuple[int, int]:
    """Return the sample block [first, last) for the header at start, banner included."""
    first = start
    while first > 0 and lines[first - 1].startswith("#"):
        first -= 1
    last = start + 1
    while last < len(lines) and not (HEADER.match(lines[last]) or BANNER.match(lines[last])):
        last += 1
    while last > start and lines[last - 1].strip() == "":
        last -= 1
    return first, last


def main(section: str, sample_path: str, config_path: str) -> int:
    sample = Path(sample_path).read_text().splitlines()
    config = Path(config_path).read_text().splitlines()
    order = list(tomllib.loads("\n".join(sample)))
    if section not in order:
        print(f"{sample_path} has no [{section}] section", file=sys.stderr)
        return 1
    if section in tomllib.loads("\n".join(config)):
        print(f"{config_path} already has [{section}]", file=sys.stderr)
        return 1
    first, last = _block(sample, _header_lines(sample)[section])
    block = sample[first:last]
    present = _header_lines(config)
    before = [name for name in order[: order.index(section)] if name in present]
    if before:
        _, insert_at = _block(config, present[before[-1]])
    else:
        insert_at = 0
    gap = ["", ""] if insert_at else []
    config[insert_at:insert_at] = gap + block
    Path(config_path).write_text("\n".join(config) + "\n")
    start = insert_at + len(gap) + 1
    print(f"[{section}] inserted at lines {start}-{start + len(block) - 1} of {config_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
