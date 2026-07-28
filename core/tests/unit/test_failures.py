"""Classifying an exception into the failure it actually is.

The point of the module under test is that a catch-all arm must not report
every environmental condition as an internal defect, so these assert the
category *and* the retryability — the two facts a client acts on.
"""

from __future__ import annotations

import errno

import pytest

from repo2ree_core.failures import classify, failed_from_exception


def _os_error(code: int) -> OSError:
    return OSError(code, "synthetic")


def test_a_full_volume_is_environmental_and_worth_retrying():
    result = failed_from_exception(_os_error(errno.ENOSPC), "write_file failed: no space")

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "unavailable"
    assert result.failure.retryable is True
    # The symbolic name, because whoever reads this is diagnosing it.
    assert result.failure.details == {"errno": "ENOSPC"}
    # The handler's message survives: only it knows which operation failed.
    assert result.failure.message == "write_file failed: no space"


def test_a_read_only_mount_is_environmental_but_not_retryable():
    category, retryable = classify(_os_error(errno.EROFS))

    assert category == "unavailable"
    # Nothing changes until the deployment is fixed, so a retry only burns a run.
    assert retryable is False


def test_a_missing_path_is_a_precondition_not_a_fault():
    assert classify(_os_error(errno.ENOENT)) == ("precondition", False)


def test_permission_errors_stay_internal_by_intent():
    # A mis-mounted volume or wrong uid is a deployment defect: nothing the
    # caller can act on, and not worth a retry.
    assert classify(_os_error(errno.EACCES)) == ("internal", False)
    assert classify(_os_error(errno.EPERM)) == ("internal", False)


def test_a_timed_out_call_is_a_timeout_despite_being_an_os_error():
    # TimeoutError subclasses OSError, so order of matching is what decides
    # this — and the timeout category exists precisely for it.
    assert isinstance(TimeoutError(), OSError)
    assert classify(TimeoutError("read timed out")) == ("timeout", True)


@pytest.mark.parametrize(
    "code",
    [errno.ECONNRESET, errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH, errno.EPIPE],
)
def test_an_unreachable_dependency_is_retryable(code: int):
    assert classify(_os_error(code)) == ("unavailable", True)


def test_an_unmapped_errno_keeps_the_conservative_default():
    # A confidently wrong category is worse than a coarse one.
    category, retryable = classify(_os_error(errno.EILSEQ))
    assert category == "internal"
    assert retryable is False


def test_a_non_os_error_is_an_internal_fault_with_no_errno_detail():
    result = failed_from_exception(ValueError("bad state"), "seal_ree failed: bad state")

    assert result.failure is not None
    assert result.failure.category == "internal"
    assert result.failure.retryable is False
    assert result.failure.details is None


def test_an_os_error_without_an_errno_is_still_internal():
    # OSError() with no code — reachable through libraries that raise it bare.
    assert classify(OSError("unspecified")) == ("internal", False)


def test_origin_and_outputs_are_carried_through():
    result = failed_from_exception(
        _os_error(errno.ENOSPC),
        "staging failed",
        origin="api",
        outputs={"upload_token": "tok-1"},
    )

    assert result.failure is not None
    assert result.failure.origin == "api"
    assert result.outputs == {"upload_token": "tok-1"}
    # The ActionResult invariant holds: a failure never reports exit code 0.
    assert result.exit_code != 0
