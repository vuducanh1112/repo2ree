"""Keep the removed runtime-agent vocabulary from returning to active surfaces."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCAN_ROOTS = (
    "api",
    "core",
    "executor",
    "gui/src",
    "gui/tests",
    "just",
    "nix",
    "protocol/src",
    "scripts",
    "supervisor",
    "workbench",
)
SCAN_FILES = (
    "docker-compose.yml",
    "docker-compose.workbench.yml",
    "flake.nix",
    "justfile",
    "pyproject.toml",
)
TEXT_SUFFIXES = {".css", ".json", ".mjs", ".nix", ".py", ".sh", ".toml", ".ts", ".tsx", ".yml"}

# Construct the retired term so this guard does not have to exempt itself.
RETIRED = "ag" + "ent"
VOCABULARY = re.compile(rf"(?i)\b{RETIRED}s?\b|{RETIRED}_|repo2ree_{RETIRED}")

# No retired runtime vocabulary is allowed in active code or tests.
ALLOWED_MATCHES: Counter[tuple[str, str]] = Counter()


def _files() -> list[Path]:
    files = [ROOT / relative for relative in SCAN_FILES]
    for relative in SCAN_ROOTS:
        files.extend(path for path in (ROOT / relative).rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES)
    return files


def test_active_surfaces_use_workbench_vocabulary() -> None:
    found: Counter[tuple[str, str]] = Counter()
    details: list[str] = []
    for path in _files():
        relative = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in VOCABULARY.finditer(line):
                normalized = (
                    f"{RETIRED}_" if match.group(0).lower().startswith(f"{RETIRED}_") else match.group(0).lower()
                )
                found[(relative, normalized)] += 1
                details.append(f"{relative}:{line_number}: {line.strip()}")

    assert found == ALLOWED_MATCHES, "legacy runtime vocabulary changed:\n" + "\n".join(details)
