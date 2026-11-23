from __future__ import annotations

import errno
from typing import Any

from repo2ree_protocol.result import ActionResult, FailureCategory, FailureOrigin

_BY_ERRNO: dict[int, tuple[FailureCategory, bool]] = {
    errno.ENOSPC: ("unavailable", True),
    errno.EDQUOT: ("unavailable", True),
    errno.EMFILE: ("unavailable", True),
    errno.ENFILE: ("unavailable", True),
    errno.EAGAIN: ("unavailable", True),
    errno.ECONNRESET: ("unavailable", True),
    errno.ECONNREFUSED: ("unavailable", True),
    errno.EHOSTUNREACH: ("unavailable", True),
    errno.ENETUNREACH: ("unavailable", True),
    errno.EPIPE: ("unavailable", True),
    errno.EROFS: ("unavailable", False),
    errno.EACCES: ("internal", False),
    errno.EPERM: ("internal", False),
    errno.ENOENT: ("precondition", False),
    errno.ENOTDIR: ("precondition", False),
    errno.EISDIR: ("precondition", False),
}


def classify(exc: BaseException) -> tuple[FailureCategory, bool]:
    if isinstance(exc, TimeoutError):
        return ("timeout", True)
    if isinstance(exc, OSError) and exc.errno is not None:
        return _BY_ERRNO.get(exc.errno, ("internal", False))
    return ("internal", False)


def failed_from_exception(
    exc: BaseException,
    message: str,
    *,
    origin: FailureOrigin = "core",
    outputs: dict[str, Any] | None = None,
) -> ActionResult:
    category, retryable = classify(exc)
    details: dict[str, Any] | None = None
    if isinstance(exc, OSError) and exc.errno is not None:
        details = {"errno": errno.errorcode.get(exc.errno, exc.errno)}
    return ActionResult.failed(
        category,
        message,
        origin=origin,
        retryable=retryable,
        details=details,
        outputs=outputs,
    )
