"""Per-run receipts: input digests recorded at execution time.

A receipt binds one executed run to the inputs it ran against (as a
re-runner will have them: the *materialization inputs*, never the live
workspace tree) and to the outputs it produced. Receipts are evidence
against accidents — stale inputs, a wrong artifact wired up — not
attestation against adversarial authors. They are provenance records,
never cache keys.

One receipt file per run, ``runs/<run_id>.receipt.json``, sibling of the
NDJSON run log. The envelope fields (schema version, run id, operation,
timestamp, status) are uniform across operations so callers can select
"latest successful receipt per step" without parsing operation-specific
bodies; the input/output slices are operation-specific and typed, so the
seal-time check and any later classifier can match exhaustively instead
of probing key conventions.

Also home to the materialization marker and the workspace-drift check
(detect, don't identify: a workspace that drifted from
``materialize(snapshot + overlay)`` cannot be reproduced by the bundle's
replay even in principle), and the seal-time consistency report.
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from repo2ree_core.digests import (
    digest_file,
    digest_file_if_exists,
    digest_output_paths,
    digest_tree,
)
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.experiment.experiment import Runnable
from repo2ree_core.path_safety import WORKSPACE_CONTROL_PREFIXES
from repo2ree_core.reserved_paths import experiment_slug
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionStatus

RECEIPT_SCHEMA_VERSION: Literal[1] = 1

# Paths listed in a drift verdict are capped so a wholesale workspace change
# cannot balloon the receipt; the status alone carries the verdict.
_DRIFT_PATHS_CAP = 20

# generate_sbom writes this into the workspace at a fixed name (the sbom path
# is also declared on the intent).
_SBOM_TOOL_OUTPUTS = ("sbom.json",)


class _ReceiptModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ================================================
# Workspace drift
# ================================================


DriftStatus = Literal["clean", "modified", "unknown"]


class WorkspaceDrift(_ReceiptModel):
    """Whether the workspace still equals ``materialize(snapshot + overlay)``.

    ``unknown`` means there was no materialization marker to check against
    (the workspace was never materialized through the tracked path).
    ``changed_paths`` is capped; ``changed_path_count`` carries the true count.
    """

    status: DriftStatus
    changed_paths: list[str] = Field(default_factory=list)
    changed_path_count: int = 0


# ================================================
# Receipt models — shared envelope + per-operation slices
# ================================================


class _ReceiptEnvelope(_ReceiptModel):
    """Fields uniform across every operation's receipt.

    Selection ("latest successful receipt per step") only ever needs these,
    so scanning ``runs/`` never depends on operation-specific bodies.
    """

    schema_version: Literal[1] = RECEIPT_SCHEMA_VERSION
    run_id: str
    started_at: str
    finished_at: str
    duration_ms: int = Field(ge=0)
    recorded_at: str
    status: ActionStatus


class AcquireSourceReceipt(_ReceiptEnvelope):
    """Chain root: no inputs, records what was acquired."""

    operation: Literal["acquire_source"] = "acquire_source"
    origin_url: str = ""
    source_type: str = ""
    revision: str = ""


class SnapshotUpstreamReceipt(_ReceiptEnvelope):
    operation: Literal["snapshot_upstream"] = "snapshot_upstream"
    snapshot_digest: str | None = None


class BuildRuntimeReceipt(_ReceiptEnvelope):
    operation: Literal["build_runtime"] = "build_runtime"
    workspace_drift: WorkspaceDrift | None = None
    # Input slice
    snapshot_digest: str | None = None
    build_script_path: str = ""
    build_script_digest: str | None = None
    # Produced output
    runtime_path: str | None = None
    produced_runtime_digest: str | None = None


class GenerateSbomReceipt(_ReceiptEnvelope):
    """Workspace-independent: consumes only the declared runtime artifact."""

    operation: Literal["generate_sbom"] = "generate_sbom"
    # Input slice
    runtime_path: str = ""
    declared_runtime_digest: str | None = None
    # Produced output
    sbom_path: str | None = None
    sbom_digest: str | None = None
    # Provenance of the scan itself — what "observed" means depends on both.
    sbom_format: str | None = None
    tool_version: str | None = None


class CrossCheckSbomReceipt(_ReceiptEnvelope):
    """Aggregates of the SBOM ↔ declared-inventory cross-check.

    Carries only counts plus the digest of the SBOM it consumed: the digest
    chain (this → ``GenerateSbomReceipt.sbom_digest`` → build receipt) ties
    the verdict to the built runtime; per-dependency detail stays in the
    report artifact.
    """

    operation: Literal["cross_check_sbom"] = "cross_check_sbom"
    # Input slice
    sbom_digest: str | None = None
    # Aggregates
    declared_direct_total: int = 0
    observed_matched: int = 0
    version_mismatches: int = 0
    undeclared_same_ecosystem: int = 0
    observed_total: int = 0


class _RunnableReceipt(_ReceiptEnvelope):
    """Shared slice for activation and experiments (both are runnables).

    ``declared_runtime_digest`` is the declared tier only: it proves the
    artifact's state at run time, not that the script used it. A pass verdict
    is relative to the verify script, so its digest is part of the input
    slice alongside the run script's.
    """

    workspace_drift: WorkspaceDrift | None = None
    snapshot_digest: str | None = None
    run_script_path: str = ""
    run_script_digest: str | None = None
    verify_script_path: str = ""
    verify_script_digest: str | None = None
    runtime_path: str | None = None
    declared_runtime_digest: str | None = None


class ActivationTestReceipt(_RunnableReceipt):
    operation: Literal["activation_test"] = "activation_test"


class RunExperimentReceipt(_RunnableReceipt):
    operation: Literal["run_experiment"] = "run_experiment"
    experiment_name: str = ""
    # Produced output: digest of the declared outputs captured after a
    # successful run. Parallels ``BuildRuntimeReceipt.produced_runtime_digest``;
    # ``None`` when the experiment declares no outputs or the run did not
    # succeed. Binds the sealed baseline to the bytes verify actually ran over.
    produced_output_digest: str | None = None


RunReceipt = Annotated[
    AcquireSourceReceipt
    | SnapshotUpstreamReceipt
    | BuildRuntimeReceipt
    | GenerateSbomReceipt
    | CrossCheckSbomReceipt
    | ActivationTestReceipt
    | RunExperimentReceipt,
    Field(discriminator="operation"),
]

_receipt_adapter: TypeAdapter[RunReceipt] = TypeAdapter(RunReceipt)


# ================================================
# Persistence
# ================================================


def receipt_run_id(run_id: str) -> str:
    """A run id safe to key a receipt file by.

    Dispatched runs carry a registry-issued unique id; manual CLI runs all
    share the literal ``"manual"``, which would make successive receipts
    overwrite each other — give those a unique suffix instead.
    """
    if run_id and run_id != "manual":
        return run_id
    return f"manual-{uuid4().hex[:12]}"


def _atomic_write(path: Path, content: str) -> None:
    """Atomically replace one receipt file with fully serialized JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def receipt_step_key(receipt: RunReceipt) -> str:
    """Stable selection key: operation, except experiments are keyed by name."""
    if isinstance(receipt, RunExperimentReceipt):
        return f"experiment:{receipt.experiment_name}"
    return receipt.operation


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
        content = json.dumps(receipt.model_dump(), indent=2, sort_keys=True)
        _atomic_write(layout.run_receipt(receipt.run_id), content)
        if receipt.status == "succeeded":
            _atomic_write(author_receipt_path(layout, receipt), content)
    except Exception as exc:
        log("system", "warn", f"failed to record run receipt: {exc}")


def persist_snapshot_digest(store: ReeStore, digest: str | None, *, log: LogSink) -> None:
    """Record the snapshot archive's digest in the session. Never raises."""
    try:
        if not store.metadata_exists():
            return
        store.write_session(store.read_session().with_snapshot_digest(digest))
    except Exception as exc:
        log("system", "warn", f"failed to persist snapshot digest: {exc}")


def load_receipts(layout: ReeLayout) -> list[RunReceipt]:
    """All parseable receipts under ``runs/``. Unreadable files are skipped."""
    receipts: list[RunReceipt] = []
    if not layout.runs.is_dir():
        return receipts
    for path in sorted(layout.runs.glob("*.receipt.json")):
        with suppress(Exception):
            receipts.append(_receipt_adapter.validate_json(path.read_text(encoding="utf-8")))
    return receipts


def latest_successful_receipts(receipts: list[RunReceipt]) -> dict[str, RunReceipt]:
    """Latest successful receipt per step, keyed by operation (per-experiment
    for ``run_experiment``).
    """
    latest: dict[str, RunReceipt] = {}
    for receipt in receipts:
        if receipt.status != "succeeded":
            continue
        key = receipt_step_key(receipt)
        current = latest.get(key)
        # recorded_at is ISO-8601 UTC, so lexicographic order is time order.
        if current is None or receipt.recorded_at >= current.recorded_at:
            latest[key] = receipt
    return latest


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
        receipt = _receipt_adapter.validate_json(path.read_text(encoding="utf-8"))
        if isinstance(receipt, RunExperimentReceipt) or path.name != f"{receipt.operation}.json":
            raise ValueError(f"author receipt path does not match its operation: {path}")
        selected[receipt_step_key(receipt)] = receipt

    for path in experiments:
        receipt = _receipt_adapter.validate_json(path.read_text(encoding="utf-8"))
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
        *(f"experiment:{experiment.name}" for experiment in intent.experiments if experiment.name),
    ]
    return [latest[key] for key in step_keys if key in latest]


# ================================================
# Materialization marker + drift check
# ================================================


def _stat_table(workspace: Path) -> dict[str, list[int]]:
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
            "files": _stat_table(layout.workspace),
        }
        layout.materialize_marker.write_text(
            json.dumps(marker, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception as exc:
        log("system", "warn", f"failed to write materialization marker: {exc}")


def _is_control_name(rel: str) -> bool:
    return os.path.basename(rel).startswith(WORKSPACE_CONTROL_PREFIXES)


def declared_output_paths(intent: ReeIntent) -> set[str]:
    """Workspace paths that runs legitimately (re)write.

    These are excluded from drift: outputs landing inside the workspace must
    not make every step's output part of the next step's input.
    """
    paths: set[str] = set(_SBOM_TOOL_OUTPUTS)
    if intent.runtime:
        paths.add(intent.runtime)
    if intent.sbom:
        paths.add(intent.sbom)
    runnables: list[Runnable] = [intent.activation, *intent.experiments]
    for runnable in runnables:
        paths.update(runnable.output_paths)
    return paths


def check_workspace_drift(layout: ReeLayout, *, excluded_paths: set[str]) -> WorkspaceDrift:
    """Does the workspace still equal ``materialize(snapshot + overlay)``?

    Authored edits are mirrored into both overlay and workspace, so a changed
    workspace file is *not* drift when its content matches what a fresh
    materialization would produce (current overlay, else upstream). The
    marker's stat table only short-circuits content comparison for files
    untouched since materialization; stat-changed candidates are compared by
    content against their expected origin.
    """
    if not layout.materialize_marker.is_file():
        return WorkspaceDrift(status="unknown")
    try:
        marker = json.loads(layout.materialize_marker.read_text(encoding="utf-8"))
        recorded: dict[str, list[int]] = dict(marker.get("files") or {})
    except Exception:
        return WorkspaceDrift(status="unknown")

    current = _stat_table(layout.workspace)
    drifted: list[str] = []

    def is_tracked(rel: str) -> bool:
        return rel not in excluded_paths and not _is_control_name(rel)

    def expected_file(rel: str) -> Path | None:
        for base in (layout.overlay, layout.upstream):
            candidate = base / rel
            if candidate.is_file():
                return candidate
        return None

    for rel in sorted(set(recorded) | set(current)):
        if not is_tracked(rel):
            continue
        if recorded.get(rel) == current.get(rel):
            continue  # untouched since materialization
        expected = expected_file(rel)
        actual = layout.workspace / rel
        if not actual.is_file():
            # Gone from the workspace: drift only if a re-materialization
            # would restore it (it still has an origin in overlay/upstream).
            if expected is not None:
                drifted.append(rel)
            continue
        if expected is None:
            drifted.append(rel)  # residue: no origin would recreate it
            continue
        if digest_file(actual) != digest_file(expected):
            drifted.append(rel)

    if not drifted:
        return WorkspaceDrift(status="clean")
    return WorkspaceDrift(
        status="modified",
        changed_paths=drifted[:_DRIFT_PATHS_CAP],
        changed_path_count=len(drifted),
    )


def current_runtime_digest(layout: ReeLayout, runtime_path: str | None) -> str | None:
    """Digest of the declared runtime artifact, cached by its stat facts.

    The runtime tar is multi-gigabyte and the consistency report rides in the
    workspace payload fetched on every page load, so re-hashing per request is
    not an option. The cache is invalidated by the same (path, size, mtime)
    facts the drift check trusts; cache I/O failures fall back to hashing.
    """
    if not runtime_path:
        return None
    path = layout.workspace / runtime_path
    if not path.is_file():
        return None
    stat = path.stat()
    key = {"path": runtime_path, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    with suppress(Exception):
        cached = json.loads(layout.digest_cache.read_text(encoding="utf-8"))
        if {name: cached.get(name) for name in key} == key and cached.get("digest"):
            return str(cached["digest"])
    digest = digest_file(path)
    with suppress(Exception):
        layout.digest_cache.write_text(json.dumps({**key, "digest": digest}), encoding="utf-8")
    return digest


# ================================================
# Seal-time consistency report
# ================================================


class ConsistencyStaleInput(BaseModel):
    """One input whose recorded digest disagrees with the current tree."""

    model_config = ConfigDict(extra="forbid")

    input: str
    recorded: str | None
    current: str | None


class ConsistencyStep(BaseModel):
    """Freshness of one step's latest successful receipt vs. the current tree."""

    model_config = ConfigDict(extra="forbid")

    step: str
    status: Literal["fresh", "stale", "missing"]
    run_id: str | None = None
    recorded_at: str | None = None
    stale_inputs: list[ConsistencyStaleInput] = Field(default_factory=list)
    workspace_drift: DriftStatus | None = None


class ConsistencyReport(BaseModel):
    """Per-step freshness of recorded run receipts vs. the current tree."""

    model_config = ConfigDict(extra="forbid")

    steps: list[ConsistencyStep] = Field(default_factory=list)


class AuthorReceiptEntry(BaseModel):
    """One selected author receipt joined to its live freshness verdict."""

    model_config = ConfigDict(extra="forbid")

    key: str
    receipt: RunReceipt
    consistency: ConsistencyStep


class AuthorReceiptSet(BaseModel):
    """Latest successful, fully typed author evidence for the REE."""

    model_config = ConfigDict(extra="forbid")

    receipts: list[AuthorReceiptEntry] = Field(default_factory=list)


def _compare(
    stale_inputs: list[ConsistencyStaleInput],
    input_name: str,
    recorded: str | None,
    current: str | None,
) -> None:
    """Append a stale-input record when a digest pair disagrees.

    A pair where both sides are ``None`` (input not applicable then or now)
    is not a disagreement.
    """
    if recorded == current:
        return
    stale_inputs.append(ConsistencyStaleInput(input=input_name, recorded=recorded, current=current))


def _step_report(step: str, receipt: RunReceipt | None, stale_inputs: list[ConsistencyStaleInput]) -> ConsistencyStep:
    if receipt is None:
        return ConsistencyStep(step=step, status="missing")
    drift = getattr(receipt, "workspace_drift", None)
    return ConsistencyStep(
        step=step,
        status="stale" if stale_inputs else "fresh",
        run_id=receipt.run_id,
        recorded_at=receipt.recorded_at,
        stale_inputs=stale_inputs,
        workspace_drift=drift.status if drift is not None else None,
    )


def build_consistency_report(layout: ReeLayout, intent: ReeIntent, session: Any) -> ConsistencyReport:
    """Per-step freshness of recorded receipts against the tree being sealed.

    For every step the bundle's replay will re-execute, compare the latest
    successful receipt's input slice with the current digests: which input
    moved is named alongside the digest pair, so a 2030 re-runner can see
    "build stale: build script changed" instead of chasing ecosystem drift.
    Purely informational — sealing over stale results proceeds; recording the
    inconsistency is the point.
    """
    latest = load_author_receipts(layout)
    snapshot_digest = getattr(session, "source_snapshot_digest", None)
    runtime_digest = current_runtime_digest(layout, intent.runtime)

    steps: list[ConsistencyStep] = []

    build = latest.get("build_runtime")
    stale: list[ConsistencyStaleInput] = []
    if isinstance(build, BuildRuntimeReceipt):
        _compare(stale, "snapshot", build.snapshot_digest, snapshot_digest)
        _compare(
            stale,
            "build_script",
            build.build_script_digest,
            digest_file_if_exists(layout.workspace / build.build_script_path) if build.build_script_path else None,
        )
        _compare(stale, "runtime_artifact", build.produced_runtime_digest, runtime_digest)
    steps.append(_step_report("build_runtime", build, stale))

    sbom = latest.get("generate_sbom")
    stale = []
    if isinstance(sbom, GenerateSbomReceipt):
        _compare(stale, "runtime_artifact", sbom.declared_runtime_digest, runtime_digest)
    steps.append(_step_report("generate_sbom", sbom, stale))

    activation = latest.get("activation_test")
    stale = []
    if isinstance(activation, ActivationTestReceipt):
        _compare(stale, "snapshot", activation.snapshot_digest, snapshot_digest)
        _compare(
            stale,
            "activation_script",
            activation.run_script_digest,
            digest_file_if_exists(layout.workspace / intent.activation.run_script)
            if intent.activation.run_script
            else None,
        )
        _compare(
            stale,
            "verify_script",
            activation.verify_script_digest,
            digest_file_if_exists(layout.workspace / intent.activation.verify_script)
            if intent.activation.verify_script
            else None,
        )
        _compare(stale, "runtime_artifact", activation.declared_runtime_digest, runtime_digest)
    steps.append(_step_report("activation_test", activation, stale))

    for experiment in intent.experiments:
        if not experiment.name:
            continue
        key = f"experiment:{experiment.name}"
        receipt = latest.get(key)
        stale = []
        if isinstance(receipt, RunExperimentReceipt):
            _compare(stale, "snapshot", receipt.snapshot_digest, snapshot_digest)
            _compare(
                stale,
                "experiment_script",
                receipt.run_script_digest,
                digest_file_if_exists(layout.workspace / experiment.run_script) if experiment.run_script else None,
            )
            _compare(
                stale,
                "verify_script",
                receipt.verify_script_digest,
                digest_file_if_exists(layout.workspace / experiment.verify_script)
                if experiment.verify_script
                else None,
            )
            _compare(stale, "runtime_artifact", receipt.declared_runtime_digest, runtime_digest)
            # Mutation gap: the declared outputs verify ran over may have been
            # rewritten in the shared workspace since this receipt was recorded.
            _compare(
                stale,
                "produced_output",
                receipt.produced_output_digest,
                digest_output_paths(layout.workspace, experiment.output_paths),
            )
        steps.append(_step_report(key, receipt, stale))

    # No timestamp here: the report must be a pure function of tree + receipts
    # so re-sealing unchanged content reproduces the same seal hash. The seal's
    # own sealedAt already dates the check.
    return ConsistencyReport(steps=steps)


def build_author_receipt_set(layout: ReeLayout, intent: ReeIntent, session: Any) -> AuthorReceiptSet:
    """Join selected author receipts to the existing consistency projection."""
    selected = load_author_receipts(layout)
    consistency = {step.step: step for step in build_consistency_report(layout, intent, session).steps}
    ordered_keys = [
        "acquire_source",
        "snapshot_upstream",
        "build_runtime",
        "generate_sbom",
        "cross_check_sbom",
        "activation_test",
        *(f"experiment:{experiment.name}" for experiment in intent.experiments if experiment.name),
    ]
    entries: list[AuthorReceiptEntry] = []
    for key in ordered_keys:
        receipt = selected.get(key)
        if receipt is None:
            continue
        entries.append(
            AuthorReceiptEntry(
                key=key,
                receipt=receipt,
                consistency=consistency.get(key, _step_report(key, receipt, [])),
            )
        )
    return AuthorReceiptSet(receipts=entries)
