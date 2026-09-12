from __future__ import annotations

import time

from repo2ree_core.bundle.seal import BundleProgress, BundleSealCanceledError, seal_ree
from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.time_utils import utc_now_instant
from repo2ree_protocol.command import SealReeArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def _format_bytes(value: int) -> str:
    amount = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{value} B"
            return f"{amount:.1f} {unit}"
        amount /= 1024
    raise AssertionError("unreachable")  # pragma: no cover


class _ProgressLogger:
    """Turn per-chunk progress into a small, useful run-log stream."""

    def __init__(self, log: LogSink) -> None:
        self._log = log
        self._last_phase: str | None = None
        self._last_percent = -5
        self._last_bytes = 0
        self._last_at = 0.0
        self._reported_complete = False

    def __call__(self, update: BundleProgress) -> None:
        now = time.monotonic()
        percent = 100 if update.bytes_total == 0 else update.bytes_processed * 100 // update.bytes_total
        phase_changed = update.phase != self._last_phase
        due = (
            phase_changed
            or percent >= self._last_percent + 5
            or update.bytes_processed >= self._last_bytes + 64 * 1024 * 1024
            or now >= self._last_at + 5
            or (
                not self._reported_complete
                and update.bytes_processed == update.bytes_total
                and update.entries_processed == update.entries_total
            )
        )
        if not due:
            return

        if update.phase == "writing":
            message = (
                f"Preparing sealed artifacts: {_format_bytes(update.bytes_processed)} / "
                f"{_format_bytes(update.bytes_total)} "
                f"({percent}%), {update.entries_processed}/{update.entries_total} entries"
            )
        elif update.phase == "manifest":
            message = "Writing sealed manifest"
        else:
            message = "Publishing sealed repository state"
        self._log("system", "info", message)
        self._last_phase = update.phase
        self._last_percent = percent
        self._last_bytes = update.bytes_processed
        self._last_at = now
        self._reported_complete = (
            update.bytes_processed == update.bytes_total and update.entries_processed == update.entries_total
        )


def handle_seal_ree(
    args: SealReeArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()

    try:
        outputs = seal_ree(
            layout,
            source_included=args.source_included,
            runtime_included=args.runtime_included,
            results_included=args.results_included,
            sealed_at=utc_now_instant(),
            progress=_ProgressLogger(log),
            is_canceled=is_canceled,
        )
    except BundleSealCanceledError:
        log("system", "warn", "REE sealing canceled")
        return ActionResult(status="canceled")
    except ReePreconditionError as exc:
        # The REE is not in a state that may be sealed — the author's own tree
        # said so, and no retry changes that until they act on it.
        log("system", "error", f"seal_ree refused: {exc}")
        return ActionResult.failed("precondition", str(exc))
    except Exception as exc:
        log("system", "error", f"seal_ree failed: {exc}")
        return failed_from_exception(exc, f"seal_ree failed: {exc}")

    log(
        "system",
        "info",
        f"REE sealed: {outputs.ree_digest} ({_format_bytes(outputs.input_bytes)}, {outputs.entry_count} entries)",
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))
