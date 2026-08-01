"""Persisted receipt records and the materialization marker beside them.

One receipt file per run, ``runs/<run_id>.receipt.json``, sibling of the NDJSON
run log — immutable history. Every *successful* run additionally replaces its
step's selected receipt under ``receipts/author``, which is the authoritative
set: history in ``runs/`` is never promoted implicitly, since doing so would
resurrect invalidated evidence after a source reset.

Also home to the materialization marker — the record of what the workspace was
materialized from, which ``consistency`` walks to decide whether it still is.

Imperative shell: every function here touches the filesystem.
"""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from repo2ree_core.digests import Digest, digest_tree
from repo2ree_core.domain.receipt import (
    RunExperimentReceipt,
    RunReceipt,
    experiment_step_key,
    receipt_adapter,
    receipt_step_key,
)
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import record_snapshot_digest
from repo2ree_core.ree.files import json_document_bytes, write_atomic, write_json_atomic
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.reserved_paths import experiment_slug
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import LogSink


def author_receipt_path(layout: ReeLayout, receipt: RunReceipt) -> Path:
    """Deterministic selected-author-receipt path for ``receipt``."""
    if isinstance(receipt, RunExperimentReceipt):
        return layout.author_experiment_receipt(experiment_slug(receipt.experiment_name))
    return layout.author_operation_receipt(receipt.operation)


def record_receipt(layout: ReeLayout, receipt: RunReceipt, *, log: LogSink) -> None:
    """Persist immutable history and select successful author evidence. Never raises.

    A receipt is evidence, not a gate: failing to record one must never fail
    the run it describes. Every attempt lands beside its run log; only a
    successful attempt atomically replaces the operation's selected receipt
    under ``receipts/author``.
    """
    try:
        # Serialized once and written twice: history and the selected receipt
        # are the same bytes by construction, so no promotion can quietly
        # publish a receipt that differs from the one it was recorded as.
        content = json_document_bytes(receipt.model_dump(mode="json"))
        write_atomic(layout.run_receipt(receipt.run_id), content)
        if receipt.status == "succeeded":
            write_atomic(author_receipt_path(layout, receipt), content)
    except Exception as exc:  # noqa: BLE001 — recording evidence must never fail the run the evidence is about
        log("system", "warn", f"failed to record run receipt: {exc}")


def persist_snapshot_digest(store: ReeStore, digest: Digest | None, *, log: LogSink) -> None:
    """Record the snapshot archive's digest in the session. Never raises."""
    try:
        if not store.metadata_exists():
            return
        store.write_session(record_snapshot_digest(store.read_session(), digest))
    except Exception as exc:  # noqa: BLE001 — as the docstring says: never raises
        log("system", "warn", f"failed to persist snapshot digest: {exc}")


def load_receipts(layout: ReeLayout) -> list[RunReceipt]:
    """All parseable receipts under ``runs/``. Unreadable files are skipped."""
    receipts: list[RunReceipt] = []
    if not layout.runs.is_dir():
        return receipts
    for path in sorted(layout.runs.glob("*.receipt.json")):
        with suppress(Exception):
            receipts.append(receipt_adapter.validate_json(path.read_text(encoding="utf-8")))
    return receipts


def load_author_receipts(layout: ReeLayout) -> dict[str, RunReceipt]:
    """Load the fully typed selected author receipt for every successful step.

    ``receipts/author`` is authoritative. Immutable receipts in ``runs/`` are
    history only and must not be promoted implicitly: doing so would resurrect
    invalidated evidence after a source reset.
    """
    direct = sorted(layout.author_receipts.glob("*.json"))
    experiment_dir = layout.author_receipts / "experiments"
    experiments = sorted(experiment_dir.glob("*.json")) if experiment_dir.is_dir() else []

    selected: dict[str, RunReceipt] = {}
    for path in direct:
        receipt = receipt_adapter.validate_json(path.read_text(encoding="utf-8"))
        if isinstance(receipt, RunExperimentReceipt) or path.name != f"{receipt.operation}.json":
            raise ValueError(f"author receipt path does not match its operation: {path}")
        selected[receipt_step_key(receipt)] = receipt

    for path in experiments:
        receipt = receipt_adapter.validate_json(path.read_text(encoding="utf-8"))
        if not isinstance(receipt, RunExperimentReceipt):
            raise ValueError(f"author experiment receipt has the wrong operation: {path}")
        if path.stem != experiment_slug(receipt.experiment_name):
            raise ValueError(f"author experiment receipt path does not match its experiment: {path}")
        selected[receipt_step_key(receipt)] = receipt
    return selected


def prune_author_experiment_receipts(layout: ReeLayout, intent: ReeIntent) -> None:
    """Drop selected receipts for experiments no longer declared on the REE."""
    directory = layout.author_receipts / "experiments"
    if not directory.is_dir():
        return
    declared = {experiment_slug(experiment.name) for experiment in intent.experiments if experiment.name}
    for path in directory.glob("*.json"):
        if path.stem not in declared:
            path.unlink(missing_ok=True)


def published_receipts(layout: ReeLayout, intent: ReeIntent) -> list[RunReceipt]:
    """The selected author receipts the sealed bundle publishes.

    The bundle records the *reproducible endstate*, not authoring history —
    superseded and failed runs stay behind in the workbench ``runs/`` record.
    Experiment receipts are published only for experiments still on the
    intent. Ordered by step so bundle assembly stays deterministic.
    """
    latest = load_author_receipts(layout)
    step_keys = [
        "acquire_source",
        "snapshot_upstream",
        "build_runtime",
        "generate_sbom",
        "cross_check_sbom",
        "activation_test",
        *(experiment_step_key(experiment.name) for experiment in intent.experiments if experiment.name),
    ]
    return [latest[key] for key in step_keys if key in latest]


# ================================================
# Materialization marker
# ================================================


def stat_table(workspace: Path) -> dict[str, list[int]]:
    """``{relpath: [size, mtime_ns]}`` for every regular file in the workspace."""
    table: dict[str, list[int]] = {}
    if not workspace.is_dir():
        return table
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        table[path.relative_to(workspace).as_posix()] = [stat.st_size, stat.st_mtime_ns]
    return table


def write_materialize_marker(
    layout: ReeLayout,
    *,
    snapshot_digest: str | None,
    log: LogSink,
) -> None:
    """Record what the workspace was materialized from, and its file stats.

    The stat table is the cheap "unchanged since materialization" oracle the
    drift check walks against. Never raises: a marker failure degrades drift
    verdicts to ``unknown``, it must not fail the materialization.
    """
    try:
        marker = {
            "materialized_at": utc_now(),
            "snapshot_digest": snapshot_digest,
            "overlay_digest": digest_tree(layout.overlay),
            "files": stat_table(layout.workspace),
        }
        write_json_atomic(layout.materialize_marker, marker)
    except Exception as exc:  # noqa: BLE001 — a missing marker degrades a later drift check to unknown; it cannot fail this run
        log("system", "warn", f"failed to write materialization marker: {exc}")
