"""What an unexpected exception actually says about a failure.

A handler's ``except`` arm knows which operation failed but not what *kind* of
failure it was, and that difference is the whole value of the typed
:class:`~repo2ree_protocol.result.Failure`. Collapsing everything to
``internal`` — what every catch-all did before this module — reports "a defect
inside repo2ree, do not retry" for the conditions those arms actually catch
most often: a full workbench volume, an exhausted descriptor table, a read
racing a teardown. Those are environmental, and some of them are retryable.

The mapping is deliberately partial. Only errnos whose meaning is unambiguous
are listed; anything else keeps the conservative ``internal`` default, because
a confidently wrong category is worse than a coarse one.

Leaf primitive: imports the failure vocabulary and nothing else.
"""

from __future__ import annotations

import errno
from typing import Any

from repo2ree_protocol.result import ActionResult, FailureCategory, FailureOrigin

# errno → (category, retryable).
#
# ``retryable`` answers "may the caller safely replay this request", not "will
# it succeed next time" — a full volume is worth retrying once an operator has
# cleared it, and replaying does no harm in the meantime.
_BY_ERRNO: dict[int, tuple[FailureCategory, bool]] = {
    # Storage is exhausted. The request itself is sound and can be replayed
    # once there is room for it.
    errno.ENOSPC: ("unavailable", True),
    errno.EDQUOT: ("unavailable", True),
    # Process-wide resource exhaustion, typically transient under load: the
    # next attempt may well find the descriptor this one could not.
    errno.EMFILE: ("unavailable", True),
    errno.ENFILE: ("unavailable", True),
    errno.EAGAIN: ("unavailable", True),
    # The path to a dependency is down. Retryable by definition.
    errno.ECONNRESET: ("unavailable", True),
    errno.ECONNREFUSED: ("unavailable", True),
    errno.EHOSTUNREACH: ("unavailable", True),
    errno.ENETUNREACH: ("unavailable", True),
    errno.EPIPE: ("unavailable", True),
    # A read-only mount is environmental like the above, but nothing changes by
    # trying again — it takes a deployment fix, so retrying only wastes a run.
    errno.EROFS: ("unavailable", False),
    # Permissions are a deployment defect (a mis-mounted volume, a wrong uid),
    # not something the caller can act on. It stays `internal` by intent rather
    # than by omission, which is why it is listed.
    errno.EACCES: ("internal", False),
    errno.EPERM: ("internal", False),
    # Something the operation required is not there: the state it ran against
    # is wrong, which is a precondition rather than a fault.
    errno.ENOENT: ("precondition", False),
    errno.ENOTDIR: ("precondition", False),
    errno.EISDIR: ("precondition", False),
}


def classify(exc: BaseException) -> tuple[FailureCategory, bool]:
    """The ``(category, retryable)`` pair ``exc`` really carries."""
    # TimeoutError has been an OSError subclass since 3.10, so it has to be
    # matched ahead of the errno table — a timed-out call has its own category
    # and reaches this either with no errno or with ETIMEDOUT.
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
    """Build the failed :class:`ActionResult` that ``exc`` warrants.

    The drop-in replacement for ``ActionResult.failed("internal", …)`` in a
    catch-all arm. ``message`` stays the handler's — it names the operation,
    which the exception cannot — while the category, retryability, and the
    errno name in ``details`` come from the exception.
    """
    category, retryable = classify(exc)
    details: dict[str, Any] | None = None
    if isinstance(exc, OSError) and exc.errno is not None:
        # The symbolic name, not the number: whoever reads this failure is
        # diagnosing it, and ENOSPC says what 28 does not.
        details = {"errno": errno.errorcode.get(exc.errno, exc.errno)}
    return ActionResult.failed(
        category,
        message,
        origin=origin,
        retryable=retryable,
        details=details,
        outputs=outputs,
    )
