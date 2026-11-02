"""Correlation between a managed provider allocation and its workbench.

With a file, the expectations outlive the control plane: a bench provisioned
before a restart dials back in with the token it was given and is still known.
Only token digests are kept, the file is its owner's alone, and an entry goes
when its allocation is released.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from pathlib import Path

from repo2ree_protocol.workbench import WorkbenchHello
from repo2ree_supervisor.json_file import write_json_atomic


class EnrollmentRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._expected: dict[str, tuple[str, str]] = {}
        if path is not None and path.exists():
            stored = json.loads(path.read_text(encoding="utf-8"))
            self._expected = {allocation: (workbench, digest) for allocation, (workbench, digest) in stored.items()}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def expect(self, allocation_id: str, workbench_id: str, token: str) -> None:
        with self._lock:
            self._expected[allocation_id] = (workbench_id, self._digest(token))
            self._save()

    def authenticate(self, hello: WorkbenchHello) -> None:
        with self._lock:
            expected = self._expected.get(hello.allocation_id)
            if expected is None:
                raise ValueError("unknown workbench enrollment")
            expected_id, expected_digest = expected
            if hello.workbench_id != expected_id or not hmac.compare_digest(
                self._digest(hello.enrollment_token), expected_digest
            ):
                raise ValueError("workbench enrollment does not match its allocation")
            # Keep the expectation until teardown so the same managed workbench
            # can reconnect after a transient control-plane connection loss.

    def discard(self, allocation_id: str) -> None:
        with self._lock:
            if self._expected.pop(allocation_id, None) is not None:
                self._save()

    def _save(self) -> None:
        if self._path is not None:
            write_json_atomic(self._path, self._expected)
