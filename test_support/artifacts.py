"""One run directory shared by pytest, task recipes, and report consumers."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "test-artifacts"


def execution_id() -> str:
    return os.environ.setdefault("REPO2REE_TEST_RUN_ID", uuid4().hex)


def run_dir() -> Path:
    """Stable artifact root; execution identity lives in metadata, not paths."""
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


def case_dir(nodeid: str) -> Path:
    source, *test = nodeid.split("::")
    parts = [part for part in Path(source).with_suffix("").parts if part != "tests"]
    return run_dir() / "python/tests" / Path(*(case_key(part) for part in [*parts, *test]))


def service_dir(suite: str) -> Path:
    return run_dir() / "python/services" / case_key(suite)


def write_provenance(directory: Path, identity: str | None = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "provenance.json").write_text(json.dumps({"execution_id": identity or execution_id()}) + "\n")


def latest_path(relative: str) -> Path:
    current = run_dir() / relative
    if current.exists():
        return current
    candidates = [path for path in (ARTIFACTS / "runs").glob(f"*/{relative}") if path.exists()]
    if not candidates:
        raise FileNotFoundError(f"No recorded artifact: {relative}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def latest_test(suffix: str, filename: str) -> Path:
    candidates = []
    manifests = list((run_dir() / "python/tests").rglob("manifest.json"))
    manifests.extend((ARTIFACTS / "runs").glob("*/tests/*/manifest.json"))
    for manifest in manifests:
        document = json.loads(manifest.read_text())
        if document["nodeid"].endswith(suffix) and (manifest.parent / filename).is_file():
            candidates.append(manifest.parent / filename)
    if not candidates:
        raise FileNotFoundError(f"No recorded {filename} for {suffix}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


if __name__ == "__main__":
    if sys.argv[1:] == ["run-dir"]:
        sys.stdout.write(str(run_dir()) + "\n")
    elif len(sys.argv) == 3 and sys.argv[1] == "latest-path":
        sys.stdout.write(str(latest_path(sys.argv[2])) + "\n")
    elif len(sys.argv) == 4 and sys.argv[1] == "latest-test":
        sys.stdout.write(str(latest_test(sys.argv[2], sys.argv[3])) + "\n")
    else:
        raise SystemExit("usage: python -m test_support.artifacts run-dir | latest-test SUFFIX FILE")
