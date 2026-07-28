"""What the recorded evidence means against the tree as it stands now.

Two questions, both answered by comparing digests rather than trusting history:

*Drift* — does the workspace still equal ``materialize(snapshot + overlay)``?
Detect, don't identify: a workspace that drifted cannot be reproduced by the
bundle's replay even in principle, so naming *that* is the whole verdict.

*Freshness* — for every step the bundle's replay will re-execute, does the
latest successful receipt's input slice still match the current digests? Which
input moved is named alongside the digest pair, so a 2030 re-runner sees
"build stale: build script changed" instead of chasing ecosystem drift.

Purely informational: sealing over stale results proceeds, and recording the
inconsistency is the point. Reads the tree, writes nothing but its digest cache.
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.digests import digest_file, digest_file_if_exists, digest_output_paths
from repo2ree_core.domain.experiment import Runnable
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.evidence.receipts.models import (
    ActivationTestReceipt,
    BuildRuntimeReceipt,
    DriftStatus,
    GenerateSbomReceipt,
    RunExperimentReceipt,
    RunReceipt,
    WorkspaceDrift,
    experiment_step_key,
)
from repo2ree_core.evidence.receipts.store import load_author_receipts, stat_table
from repo2ree_core.path_safety import WORKSPACE_CONTROL_PREFIXES
from repo2ree_core.ree.files import write_json_atomic
from repo2ree_core.ree.layout import ReeLayout

_DRIFT_PATHS_CAP = 20


def _is_control_name(rel: str) -> bool:
    return os.path.basename(rel).startswith(WORKSPACE_CONTROL_PREFIXES)


def declared_output_paths(intent: ReeIntent) -> set[str]:
    """Workspace paths that runs legitimately (re)write.

    These are excluded from drift: outputs landing inside the workspace must
    not make every step's output part of the next step's input. The SBOM needs
    no exemption — it is written to ``artifacts/``, outside the workspace.
    """
    paths: set[str] = set()
    if intent.runtime:
        paths.add(intent.runtime)
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

    current = stat_table(layout.workspace)
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
        write_json_atomic(layout.digest_cache, {**key, "digest": digest})
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
        key = experiment_step_key(experiment.name)
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
        *(experiment_step_key(experiment.name) for experiment in intent.experiments if experiment.name),
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
