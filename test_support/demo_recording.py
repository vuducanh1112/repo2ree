"""Preserve the owned GUI demo's repository before release, then assemble offline."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from test_support.recording import TestRecorder


def preserve(directory: Path) -> None:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if any(item.get("status") == "recorded" for item in manifest["repositories"]):
        return  # The pre-release checkpoint is authoritative; do not replace it at teardown.
    recorder = TestRecorder(manifest["nodeid"], directory=directory / "capture")
    if manifest["mode"] == "provider":
        result = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"label=repo2ree.resource-owner={manifest['owner']}"],
            check=True,
            capture_output=True,
            text=True,
        )
        for container in result.stdout.splitlines():
            recorder.workbench(container)
    else:
        recorder.discover(Path(manifest["workbench_root"]))
    for item in recorder.repositories:
        if "path" in item:
            item["path"] = "capture/" + item["path"]
    manifest["repositories"] = recorder.repositories
    manifest["repository_captured_at"] = time.time()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    errors = [r for r in recorder.repositories if r["status"] != "recorded"]
    if not recorder.repositories or errors:
        raise RuntimeError(f"demo repository preservation incomplete: {errors}")


def finish(directory: Path, outcome: str) -> None:
    manifest_path = directory / "manifest.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text())
    manifest.update(finished=time.time(), outcome=outcome)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    # Each process has its own writer. Concatenate only after all exporters stop.
    with (directory / "traces.ndjson").open("wb") as output:
        for path in sorted((directory / "telemetry").glob("*.ndjson")):
            output.write(path.read_bytes())
            output.write(b"\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    preserve(args.directory)


if __name__ == "__main__":
    main()
