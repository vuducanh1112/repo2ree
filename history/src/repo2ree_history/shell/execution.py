"""Load serialized execution models from disk."""

import json
from pathlib import Path

from repo2ree_history.core.models import SystemExecution


def load_execution(path: Path) -> SystemExecution:
    """Read a complete JSON model or manifest.json + events.ndjson directory."""
    if path.is_dir():
        document = json.loads((path / "manifest.json").read_text())
        if "events" in document:
            raise ValueError("split manifest must not also contain events")
        document["events"] = [
            json.loads(line) for line in (path / "events.ndjson").read_text().splitlines() if line.strip()
        ]
    else:
        document = json.loads(path.read_text())
    if document.get("scope") != "workbench_lifecycle":
        raise ValueError("expected a SystemExecution master trace; raw OTel and test manifests are not master traces")
    return SystemExecution.model_validate(document)
