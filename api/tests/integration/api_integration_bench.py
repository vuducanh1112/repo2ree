"""What the api-integration tier provisions from, and what it records.

Everything here is imported *by name* from the tier's test modules, which is
why it is not in ``conftest.py``. Two suites in this run own a file called
``conftest.py`` — this tier's and the supervisor's — and pytest imports both
under the bare module name ``conftest``, so the last one imported is the one a
``from conftest import ...`` finds. Running the tiers together (``just
be-integration-tests`` does) then fails at collection with names that exist in
neither file. A uniquely named module cannot collide, the same reason
``core/tests/unit/scriptinfer_helpers.py`` is its own file.

Fixtures stay in ``conftest.py``, where pytest looks them up by name rather
than by import — they are not subject to any of this.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[3]

TEST_RESULTS_DIR = _REPO_ROOT / "test-artifacts" / "traces" / "api-integration"
# Its own namespace beside the traces, for the same reason `dist/diagrams` is
# not `dist/images`: both are captures this tier leaves behind, but a span
# record and an REE snapshot are read by different tools.
SNAPSHOT_DIR = _REPO_ROOT / "test-artifacts" / "ree-snapshots" / "api-integration"

# The bench this whole tier provisions from: upstream dind pinned by digest
# (keep in sync with the catalog default in api/src/repo2ree_api/settings.py).
# The in-test agent injects the executor/tools bundles (built by
# `just e2e-bundles`), so the tier drives the exact provisioning path
# production uses. Passed per-request like a real client; change here to point
# the tier at a different image. First run pulls the image.
WORKBENCH_IMAGE = (
    "docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6f61cacb880de2186339a524ecba1ce098dbbaceed6515"
)

EXEC_BUNDLE = _REPO_ROOT / "dist" / "bundles" / "exec"
TOOLS_BUNDLE = _REPO_ROOT / "dist" / "bundles" / "tools"


def bundles_present() -> bool:
    return (EXEC_BUNDLE / "manifest.json").is_file() and (TOOLS_BUNDLE / "manifest.json").is_file()


class ReeFilmstrip:
    """Records what the REE looked like after each authoring step.

    The trace tier answers what a run *did*; this answers what it left behind.
    Frames come from ``GET /rees/{id}/state``, which already carries the whole
    aggregate plus the audit derived from it — the audit being the point, since
    it is computed rather than stored and so exists nowhere a later reader could
    recover it. Never contents: a frame is a shape, and inlining every file
    would make the capture larger than the thing it describes.

    Labels are the caller's, because the interesting frames are named by intent
    ("build", "declare experiment") rather than by endpoint.
    """

    def __init__(self, client: TestClient, path: Path) -> None:
        self._client = client
        self._path = path
        self._index = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)

    def frame(self, ree_id: str, label: str) -> dict[str, Any]:
        response = self._client.get(f"/api/v1/rees/{ree_id}/state")
        assert response.status_code == 200, f"filmstrip frame {label!r}: {response.text}"
        state: dict[str, Any] = response.json()
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"index": self._index, "label": label, "state": state}) + "\n")
        self._index += 1
        return state
