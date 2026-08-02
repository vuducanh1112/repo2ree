"""Persisted receipt records for the immutable run history and selected evidence.

One receipt file per run, ``runs/<run_id>.receipt.json``, sibling of the NDJSON
run log — immutable history. Every *successful* run additionally replaces its
step's selected receipt under ``receipts/author``, which is the authoritative
set: history in ``runs/`` is never promoted implicitly, since doing so would
resurrect invalidated evidence after a source reset.

Imperative shell: every function here touches the filesystem.
"""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from repo2ree_core.digests import Digest
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.receipt import (
    RunExperimentReceipt,
    RunReceipt,
    experiment_step_key,
    receipt_adapter,
    receipt_step_key,
)
from repo2ree_core.domain.ree.state import record_snapshot_digest
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import json_document_bytes, write_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import experiment_slug
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


def persist_snapshot_digest(store: ReeDirectory, digest: Digest | None, *, log: LogSink) -> None:
    """Record the snapshot archive's digest in the state. Never raises."""
    try:
        if not store.sidecar_exists():
            return
        store.write_state(record_snapshot_digest(store.read_state(), digest))
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
