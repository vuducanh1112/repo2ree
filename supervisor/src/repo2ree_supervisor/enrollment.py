"""Correlation between a managed provider allocation and its workbench."""

from __future__ import annotations

import hashlib
import hmac
import threading

from repo2ree_protocol.workbench import WorkbenchHello


class EnrollmentRegistry:
    def __init__(self) -> None:
        self._expected: dict[str, tuple[str, str]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def expect(self, allocation_id: str, workbench_id: str, token: str) -> None:
        with self._lock:
            self._expected[allocation_id] = (workbench_id, self._digest(token))

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
            self._expected.pop(allocation_id, None)
