"""Locate and read the specification files."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

from repo2ree_conformance.spec import Spec, parse_spec

ROOT = Path(__file__).resolve().parents[3]
SPEC_DIR = ROOT / "specifications" / "behaviour"
GENERATED_MACHINES = ROOT / "protocol" / "src" / "repo2ree_protocol" / "behaviour" / "machines.py"


def load_spec(directory: Path = SPEC_DIR) -> Spec:
    def documents(subdirectory: str) -> list[dict[str, object]]:
        return [tomllib.loads(path.read_text()) for path in sorted((directory / subdirectory).glob("*.toml"))]

    def single(name: str) -> dict[str, object]:
        path = directory / name
        return tomllib.loads(path.read_text()) if path.exists() else {}

    return parse_spec(
        documents("entities"), documents("boundaries"), single("invariants.toml"), single("components.toml")
    )


def load_spec_at(revision: str, executable: str = "git") -> Spec:
    """The specification as committed at a Git revision, for reviewing behavioural changes."""
    relative = SPEC_DIR.relative_to(ROOT).as_posix()

    def run(*args: str) -> str:
        return subprocess.run([executable, "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout

    paths = run("ls-tree", "-r", "--name-only", revision, "--", relative).split()
    documents = {path: tomllib.loads(run("show", f"{revision}:{path}")) for path in paths if path.endswith(".toml")}

    def under(subdirectory: str) -> list[dict[str, object]]:
        prefix = f"{relative}/{subdirectory}/"
        return [document for path, document in sorted(documents.items()) if path.startswith(prefix)]

    return parse_spec(
        under("entities"),
        under("boundaries"),
        documents.get(f"{relative}/invariants.toml", {}),
        documents.get(f"{relative}/components.toml", {}),
    )
