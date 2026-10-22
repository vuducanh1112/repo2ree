"""One run directory shared by pytest, task recipes, and report consumers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

# The package is installed editable from testbed/src, so the repository is three levels up.
ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "test-artifacts"


def execution_id() -> str:
    return os.environ.setdefault("REPO2REE_TEST_RUN_ID", uuid4().hex)


def run_dir() -> Path:
    execution_id()
    path = Path(os.environ.get("REPO2REE_TEST_RUN_DIR", str(ARTIFACTS))).resolve()
    os.environ["REPO2REE_TEST_RUN_DIR"] = str(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def case_key(name: str) -> str:
    encoded = quote(name, safe="._-[]")
    if encoded in {"", ".", ".."}:
        encoded = encoded.replace(".", "%2E") or "%00"
    if len(encoded) > 180:
        return f"{encoded[:140]}-{hashlib.sha256(name.encode()).hexdigest()[:12]}"
    return encoded


def artifact_domain(nodeid: str) -> str:
    source = Path(nodeid.split("::", 1)[0])
    if source.is_absolute() and source.is_relative_to(ROOT):
        source = source.relative_to(ROOT)
    return "assurance" if source.parts and source.parts[0] == "conformance" else "python"


def domain_dir(domain: str) -> Path:
    if domain == "assurance":
        return Path(os.environ.get("REPO2REE_ASSURANCE_DIR", str(run_dir() / "assurance"))).resolve()
    return run_dir() / domain


def case_dir(nodeid: str) -> Path:
    source, *test = nodeid.split("::")
    path = Path(source)
    if path.is_absolute() and path.is_relative_to(ROOT):
        path = path.relative_to(ROOT)
    domain = artifact_domain(nodeid)
    parts = [part for part in path.with_suffix("").parts if part != "tests"]
    return domain_dir(domain) / "tests" / Path(*(case_key(part) for part in [*parts, *test]))


def service_dir(suite: str) -> Path:
    return run_dir() / "python/services" / case_key(suite)


def write_provenance(directory: Path, identity: str | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "provenance.json").write_text(json.dumps({"execution_id": identity or execution_id()}) + "\n")
