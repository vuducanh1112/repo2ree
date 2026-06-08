"""Action receipt — the durable record of one structural REE operation.

The journal (``/ree/receipts/journal.ndjson``) stores two NDJSON entries per
operation, discriminated by a ``type`` field:

``ReceiptOpen``  — written *before* execution (write-ahead entry).  Contains
the action_digest and input_digest, which together identify exactly what was
asked and what the overlay tree looked like before the action ran.  If the
executor crashes after the open is written but before the close is written, the
open entry is a checkpoint: the reader can compare its ``input_digest`` against
the current overlay tree to determine whether the action's side effects were
actually applied.

``ReceiptClose`` — written *after* execution (finalization entry).  Contains
the outcome (status, exit_code, outputs), the elapsed time, and
``output_digest`` — the REE state digest taken immediately after the action
completes.  Together with ``input_digest`` from the open entry, this forms
a verifiable before/after pair: ``output_digest(N-1) == input_digest(N)``
is the chain invariant.

``ActionReceipt`` is the *assembled view* returned by ``ReceiptJournal.read_all``.
It is not written to the journal directly; it is composed from a matched
open+close pair.  This is the shape the API and frontend consume.

Only *structural* operations are journaled.  ``patch_ree_intent`` and
``remove_source`` are excluded (see ``NON_JOURNALED_OPERATIONS``).

**Action-digest stability**
Large command arguments are elided in the stored open entry by the executor
(see ``repo2ree_executor.journal``); the ``action_digest`` is computed over the
*full* command before elision.  A verifier replaying from a sealed bundle must
reconstruct elided values from ``overlay/`` to recompute and check
``action_digest``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# ================================================
# Constants
# ================================================


# remove_source intentionally excluded: it resets the REE to a sourceless state,
# making prior structural ops moot. All other operations are journaled.
NON_JOURNALED_OPERATIONS: frozenset[str] = frozenset(
    {
        "patch_ree_intent",  # 300 ms-debounce autosave; control-plane state, not creation step
        "remove_source",  # structural reset — prior journal entries become meaningless
    }
)

# ================================================
# Journal entry models (written to NDJSON)
# ================================================


class ReceiptOpen(BaseModel):
    """Write-ahead entry appended to the journal *before* an action executes.

    Writing this entry before execution means a crash between open and close
    leaves a detectable dangling open.  The ``input_digest`` records the overlay
    tree state at that moment; a reader can compare it against the current tree
    to determine whether the action's side effects were applied.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["open"] = "open"
    receipt_id: str
    operation: str
    command: dict[str, Any]
    # sha256 of the canonical command JSON over the *unredacted* command.
    action_digest: str
    # reetree-v1 digest of the full REE state (upstream + overlay + intent)
    # before this action ran.  Computed by snapshot_ree_digest().
    input_digest: str | None = None
    started_at: str
    predecessor: str | None = None
    log_ref: str | None = None


class ReceiptClose(BaseModel):
    """Finalization entry appended to the journal *after* an action completes.

    If the close write itself fails the executor attempts to write an
    ``abort-close`` (same receipt_id, status="failed") so the open does not
    remain dangling.  A dangling open (open without close) means the action's
    outcome is unknown and the REE should be treated as a checkpoint boundary.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["close"] = "close"
    receipt_id: str
    status: Literal["succeeded", "failed", "canceled"]
    exit_code: int = 0
    # Large string values are elided by the executor before journal write
    # (see ``repo2ree_executor.journal.elide_large_outputs``).
    outputs: dict[str, Any] = {}
    finished_at: str
    # reetree-v1 digest of the full REE state after this action completed.
    # Computed by snapshot_ree_digest() immediately after execution.
    output_digest: str | None = None


# ================================================
# Assembled view (not written to journal directly)
# ================================================


class ActionReceipt(BaseModel):
    """Assembled view of a matched ReceiptOpen + ReceiptClose pair.

    Constructed by ``ReceiptJournal.read_all``; not written to the journal
    directly.  This is the shape consumed by the API and frontend.
    """

    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    operation: str
    command: dict[str, Any]
    action_digest: str
    input_digest: str | None = None
    output_digest: str | None = None
    status: Literal["succeeded", "failed", "canceled"]
    exit_code: int = 0
    outputs: dict[str, Any] = {}
    started_at: str
    finished_at: str
    predecessor: str | None = None
    log_ref: str | None = None


# ================================================
# Helpers
# ================================================


def compute_action_digest(command_dict: dict[str, Any]) -> str:
    """sha256 of the canonical JSON of a command dict (sorted keys, no spaces)."""
    canonical = json.dumps(command_dict, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
