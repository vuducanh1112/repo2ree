"""ReceiptJournal — two-phase append-only NDJSON log of structural REE operations.

Each operation produces two lines in ``receipts/journal.ndjson``:

  ``{"type":"open", "receipt_id":"...", ...}``   — written before execution
  ``{"type":"close","receipt_id":"...", ...}``   — written after execution

A matched open+close pair is a complete record.  An open without a close is a
*dangling open*: the action was started but the executor could not confirm the
outcome (crash, disk full, etc.).  The open's ``input_digest`` records the
overlay tree state before the action, so a verifier can compare the current
tree to determine whether the action's side effects were actually applied.

``read_all`` assembles matched pairs into ``ActionReceipt`` objects in the
order their opens appear in the journal.  Dangling opens are logged as
warnings and omitted from the assembled list, but are accessible via
``dangling_open()``.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from repo2ree_core.storage.layout import ReeLayout
from repo2ree_protocol.receipt import ActionReceipt, ReceiptClose, ReceiptOpen

_log = logging.getLogger(__name__)


def _parse_line(raw: str) -> ReceiptOpen | ReceiptClose | None:
    """Parse one NDJSON line into a typed entry; return None if invalid."""
    try:
        obj: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return None
    entry_type = obj.get("type")
    try:
        if entry_type == "open":
            return ReceiptOpen.model_validate(obj)
        if entry_type == "close":
            return ReceiptClose.model_validate(obj)
    except Exception:
        pass
    return None


class ReceiptJournal:
    """Storage semantics for the per-REE receipt journal."""

    def __init__(self, layout: ReeLayout) -> None:
        self._layout = layout

    # ------------------------------------------------
    # Writers
    # ------------------------------------------------

    def append_open(self, open_receipt: ReceiptOpen) -> None:
        """Append a write-ahead open entry, creating receipts/ if needed.

        The entry and the directory that holds it are fsynced before returning
        so the open is durable before the action executes.  This is what makes
        the write-ahead guarantee meaningful across a host power loss.
        """
        receipts_dir = self._layout.receipts
        dir_existed = receipts_dir.exists()
        receipts_dir.mkdir(parents=True, exist_ok=True)
        with self._layout.receipts_journal.open("a", encoding="utf-8") as jf:
            jf.write(open_receipt.model_dump_json() + "\n")
            jf.flush()
            os.fsync(jf.fileno())
        if not dir_existed:
            # Fsync the directory so the new receipts/ entry is durable.
            dir_fd = os.open(str(receipts_dir), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

    def append_close(self, close_receipt: ReceiptClose) -> None:
        """Append a finalization close entry."""
        self._layout.receipts.mkdir(parents=True, exist_ok=True)
        with self._layout.receipts_journal.open("a", encoding="utf-8") as jf:
            jf.write(close_receipt.model_dump_json() + "\n")

    # ------------------------------------------------
    # Readers
    # ------------------------------------------------

    def last_receipt_id(self) -> str | None:
        """Return the receipt_id of the most recent *close* entry.

        Used for predecessor chaining: only a closed receipt is a valid
        predecessor (a dangling open represents an unresolved checkpoint, not a
        completed action).

        Scans lines in reverse; logs a warning and continues past corrupt lines
        so a torn tail never silently breaks the chain.
        """
        journal = self._layout.receipts_journal
        if not journal.exists():
            return None
        with journal.open("r", encoding="utf-8", errors="replace") as jf:
            lines = [line.strip() for line in jf if line.strip()]
        if not lines:
            return None
        skipped = 0
        for line in reversed(lines):
            entry = _parse_line(line)
            if isinstance(entry, ReceiptClose):
                if skipped:
                    _log.warning(
                        "receipt journal: skipped %d line(s) scanning for last close",
                        skipped,
                    )
                return entry.receipt_id
            skipped += 1
        if skipped:
            _log.warning(
                "receipt journal: no valid close entry found (%d line(s) scanned)",
                skipped,
            )
        return None

    def dangling_open(self) -> ReceiptOpen | None:
        """Return the most recent open entry that has no matching close, or None.

        A non-None return means the previous executor process crashed between
        writing the open and writing the close.  The executor compares the open's
        ``input_digest`` against the current REE state (via ``snapshot_ree_digest``)
        to determine whether the action's side effects were applied, then writes a
        recovery close before proceeding with the next action.
        """
        opens: dict[str, ReceiptOpen] = {}
        closed_ids: set[str] = set()
        last_open_order: list[str] = []

        journal = self._layout.receipts_journal
        if not journal.exists():
            return None
        with journal.open("r", encoding="utf-8") as jf:
            for line in jf:
                entry = _parse_line(line.strip())
                if isinstance(entry, ReceiptOpen):
                    opens[entry.receipt_id] = entry
                    last_open_order.append(entry.receipt_id)
                elif isinstance(entry, ReceiptClose):
                    closed_ids.add(entry.receipt_id)

        for rid in reversed(last_open_order):
            if rid not in closed_ids:
                return opens[rid]
        return None

    def read_all(self) -> list[ActionReceipt]:
        """Assemble matched open+close pairs into ActionReceipts in journal order.

        Dangling opens are omitted from the returned list with a warning; they
        are accessible via ``dangling_open()``.  Corrupt lines are counted and
        warned about.
        """
        if not self._layout.receipts_journal.exists():
            return []

        opens: dict[str, ReceiptOpen] = {}
        closes: dict[str, ReceiptClose] = {}
        open_order: list[str] = []
        corrupt = 0

        with self._layout.receipts_journal.open("r", encoding="utf-8") as jf:
            for line in jf:
                stripped = line.strip()
                if not stripped:
                    continue
                entry = _parse_line(stripped)
                if isinstance(entry, ReceiptOpen):
                    opens[entry.receipt_id] = entry
                    open_order.append(entry.receipt_id)
                elif isinstance(entry, ReceiptClose):
                    closes[entry.receipt_id] = entry
                else:
                    corrupt += 1

        if corrupt:
            _log.warning(
                "receipt journal: skipped %d corrupt or unrecognised line(s)", corrupt
            )

        receipts: list[ActionReceipt] = []
        dangling = 0
        for rid in open_order:
            if rid not in closes:
                dangling += 1
                continue
            o = opens[rid]
            c = closes[rid]
            receipts.append(
                ActionReceipt(
                    receipt_id=rid,
                    operation=o.operation,
                    command=o.command,
                    action_digest=o.action_digest,
                    input_digest=o.input_digest,
                    output_digest=c.output_digest,
                    status=c.status,
                    exit_code=c.exit_code,
                    outputs=c.outputs,
                    started_at=o.started_at,
                    finished_at=c.finished_at,
                    predecessor=o.predecessor,
                    log_ref=o.log_ref,
                )
            )

        if dangling:
            _log.warning(
                "receipt journal: %d dangling open entry(ies) without a matching close",
                dangling,
            )

        return receipts
