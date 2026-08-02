"""Pure REE transitions: immutable values in, explicit decisions out.

Two shapes live here, and the difference between them is the point.

A *plan* is what the REE decides before anything happens: it refuses when the
REE is in no position to act, and otherwise names the effect to perform. It is
the only thing an effect may be performed from, which is what stops a handler
inventing work the aggregate never sanctioned.

An *apply* is what the REE becomes once the effect has happened and its facts
have been observed. It takes an event and returns a whole :class:`Ree`, never a
fragment — the persistence boundary saves that value, so no caller can persist
a half of a change or reassemble one itself.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.domain.primitives import (
    Digest,
    GitRevision,
    ReeId,
    ReePath,
    ReeRevision,
    ScriptPath,
    Swhid,
    UtcInstant,
)
from repo2ree_core.domain.ree.intent import SourceType
from repo2ree_core.domain.ree.model import (
    AuthoredFile,
    Ree,
    ReeDefinition,
    ReeEvidence,
    SealedRee,
)
from repo2ree_core.domain.ree.receipt import RunReceipt, receipt_step_key
from repo2ree_core.domain.ree.state import (
    ReeLifecycleState,
    SourceAcquireMode,
    record_source,
    select_packaging,
)
from repo2ree_core.domain.ree.state import (
    record_evaluation as record_state_evaluation,
)
from repo2ree_core.domain.ree.state import (
    record_seal as record_state_seal,
)
from repo2ree_core.path_safety import validate_relative_path
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT


class ReePreconditionError(ValueError):
    """The REE is not in a state where the requested move is legal.

    Distinct from a plain ``ValueError`` (a malformed request) because the two
    are different news: a precondition failure says the REE is fine and the
    request arrived at the wrong moment, so the caller's fix is to change the
    REE rather than the request. Handlers map it to the ``precondition``
    failure category on that basis.
    """


class _Transition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntentTransition(_Transition):
    before_revision: ReeRevision
    after_revision: ReeRevision
    authored: ReeDefinition
    removed_experiments: tuple[str, ...] = ()


class FileTransition(_Transition):
    before_revision: ReeRevision
    after_revision: ReeRevision
    authored: ReeDefinition
    changed_file: AuthoredFile


class RuntimeBuildTransition(_Transition):
    ree_id: ReeId
    revision: ReeRevision
    snapshot_digest: Digest | None
    build_script_path: ScriptPath
    build_script_digest: Digest


class EvidenceTransition(_Transition):
    before_revision: ReeRevision
    after_revision: ReeRevision
    authored: ReeDefinition
    evidence: ReeEvidence


class PublicationTransition(_Transition):
    revision: ReeRevision
    state: ReeLifecycleState
    publication: SealedRee | None = None


def revision_of(ree: Ree) -> ReeRevision:
    """Content identity of the REE's *head*: intent, authored files, and state.

    The head is exactly the transactional scope — the three parts one
    :func:`repo2ree_core.persistence.repository.save_ree` writes together — so
    this is what a compare-and-write can be checked against. Evidence
    (``runs/``) and the materialized workspace are deliberately excluded: both
    are append-only or derived, so neither can be lost to a concurrent writer
    and neither should invalidate a save that did not touch it.
    """
    payload = {
        "intent": ree.authored.intent.model_dump(mode="json"),
        "files": [file.model_dump(mode="json") for file in ree.authored.files],
        "state": ree.evidence.state.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return ReeRevision(f"sha256:{hashlib.sha256(encoded).hexdigest()}")


def _patch_definition(definition: ReeDefinition, patch: Mapping[str, Any]) -> ReeDefinition:
    return definition.model_copy(update={"intent": definition.intent.apply_patch(patch)})


def _definition_with_file(definition: ReeDefinition, file: AuthoredFile) -> ReeDefinition:
    remaining = (item for item in definition.files if item.path != file.path)
    return definition.model_copy(update={"files": tuple(sorted((*remaining, file), key=lambda item: item.path))})


def patch_intent(ree: Ree, patch: Mapping[str, Any]) -> IntentTransition:
    previous_names = {experiment.name for experiment in ree.authored.intent.experiments if experiment.name}
    authored = _patch_definition(ree.authored, patch)
    updated = ree.model_copy(update={"authored": authored})
    current_names = {experiment.name for experiment in authored.intent.experiments if experiment.name}
    return IntentTransition(
        before_revision=revision_of(ree),
        after_revision=revision_of(updated),
        authored=authored,
        removed_experiments=tuple(sorted(previous_names - current_names)),
    )


def write_file(ree: Ree, path: ReePath, content: bytes) -> FileTransition:
    validate_relative_path(path)
    file = AuthoredFile(
        path=path,
        digest=Digest(f"sha256:{hashlib.sha256(content).hexdigest()}"),
        size=len(content),
    )
    authored = _definition_with_file(ree.authored, file)
    updated = ree.model_copy(update={"authored": authored})
    return FileTransition(
        before_revision=revision_of(ree),
        after_revision=revision_of(updated),
        authored=authored,
        changed_file=file,
    )


def request_runtime_build(
    ree: Ree,
    *,
    snapshot_digest: Digest | None,
    build_script_digest: Digest | None,
) -> RuntimeBuildTransition:
    if build_script_digest is None:
        raise ValueError("runtime build requires the runtime build script")
    return RuntimeBuildTransition(
        ree_id=ree.identity.ree_id,
        revision=revision_of(ree),
        snapshot_digest=snapshot_digest,
        build_script_path=ScriptPath(RESERVED_BUILD_SCRIPT),
        build_script_digest=build_script_digest,
    )


# ================================================
# Source acquisition
# ================================================


class SourceRequest(_Transition):
    """What an author asked for. Nothing here has been checked yet."""

    mode: SourceAcquireMode
    origin_url: str = ""
    source_type: SourceType = ""
    # The ref the author asked for — a commit, branch, or tag — which is not
    # yet the commit it will resolve to. Empty means the origin's default HEAD.
    requested_revision: str = ""
    upload_token: str = ""
    archive_name: ReePath | None = None


class SourceSlot(_Transition):
    """What the filesystem says about the source slot, read once.

    The REE's own record of whether it has a source can disagree with the disk
    — that is precisely what an acquisition killed mid-effect leaves behind —
    so the slot is observed and passed in rather than inferred from state.
    """

    upstream_populated: bool
    snapshot_archive_present: bool
    staged_upload_present: bool


class SourcePlan(_Transition):
    """A sanctioned acquisition: the effect to perform, and what it is for.

    Carries ``before_revision`` so the save that closes the acquisition can
    check it against the head it was planned from.
    """

    ree_id: ReeId
    before_revision: ReeRevision
    mode: SourceAcquireMode
    origin_url: str = ""
    source_type: SourceType = ""
    requested_revision: str = ""
    upload_token: str = ""
    archive_name: ReePath | None = None
    snapshot_archive: ReePath


class AcquiredSource(_Transition):
    """The facts read off the tree the acquisition produced.

    Every impure read this workflow makes after its effect lands here, so the
    apply below stays a pure function of values somebody else observed.
    """

    captured_at: UtcInstant
    snapshot_digest: Digest
    resolved_commit: GitRevision | None = None
    swhid: Swhid | None = None


class SourceAcquired(_Transition):
    """One completed acquisition: what was planned, what was found, what ran."""

    plan: SourcePlan
    observed: AcquiredSource
    receipts: tuple[RunReceipt, ...] = ()


def plan_source_acquisition(
    ree: Ree,
    slot: SourceSlot,
    request: SourceRequest,
    *,
    snapshot_archive: ReePath,
) -> SourcePlan:
    """Decide whether this REE may acquire this source, and how.

    Acquisition is only legal into an empty slot. It never clears one: a source
    already present is the author's, and replacing it is a retraction they have
    to ask for. That is also what lets the disk check below mean something —
    were this to reset first, every condition it might refuse on would already
    have been erased.
    """
    if ree.publications.sealed is not None:
        raise ReePreconditionError("a sealed REE cannot acquire a source")
    if ree.evidence.state.source_available:
        raise ReePreconditionError("this REE already has a source; remove it before acquiring another")
    if slot.upstream_populated or slot.snapshot_archive_present:
        # State says no source, the disk says otherwise: an earlier acquisition
        # performed its effect and died before committing. The recovery is the
        # same retraction as for a source that did settle, so it is the same
        # instruction — there is nothing here worth a separate lifecycle.
        raise ReePreconditionError(
            "a previous acquisition left source content behind without recording it; "
            "remove the source before acquiring again"
        )

    if request.mode == "download":
        if not request.origin_url:
            raise ValueError("a download acquisition needs an origin url")
        if not request.source_type:
            raise ValueError("a download acquisition needs a source type")
    else:
        if not request.upload_token:
            raise ValueError("an upload acquisition needs an upload token")
        if request.archive_name is None:
            raise ValueError("an upload acquisition needs an archive name")
        if not slot.staged_upload_present:
            raise ReePreconditionError("the staged upload is no longer present; upload the archive again")

    return SourcePlan(
        ree_id=ree.identity.ree_id,
        before_revision=revision_of(ree),
        mode=request.mode,
        origin_url=request.origin_url if request.mode == "download" else "",
        source_type=request.source_type if request.mode == "download" else "",
        requested_revision=request.requested_revision if request.mode == "download" else "",
        upload_token=request.upload_token if request.mode == "upload" else "",
        archive_name=request.archive_name if request.mode == "upload" else None,
        snapshot_archive=snapshot_archive,
    )


def apply_source_acquired(ree: Ree, event: SourceAcquired) -> Ree:
    """The REE this acquisition leaves behind, whole.

    The resolved commit is stamped onto the intent (as the swhid is) so a
    sourceless bundle re-fetches this exact commit rather than a moving HEAD;
    it is also kept on the state as the acquisition fact it is.
    """
    plan, observed = event.plan, event.observed

    patch: dict[str, Any] = {}
    if plan.mode == "download":
        patch.update(origin_url=plan.origin_url, source_type=plan.source_type)
        if observed.resolved_commit:
            patch["revision"] = observed.resolved_commit
    if observed.swhid:
        patch["swhid"] = observed.swhid
    authored = _patch_definition(ree.authored, patch) if patch else ree.authored

    state = record_source(
        ree.evidence.state,
        acquired_by=plan.mode,
        snapshot_archive=plan.snapshot_archive,
        snapshot_captured_at=observed.captured_at,
        snapshot_digest=observed.snapshot_digest,
        archive_name=plan.archive_name,
        resolved_commit=observed.resolved_commit,
    )
    evidence = ree.evidence.model_copy(
        update={
            "state": state,
            "history": (*ree.evidence.history, *event.receipts),
            "selected": _selected_with(ree.evidence.selected, event.receipts),
        }
    )
    return ree.model_copy(update={"authored": authored, "evidence": evidence})


def _selected_with(selected: tuple[RunReceipt, ...], recorded: tuple[RunReceipt, ...]) -> tuple[RunReceipt, ...]:
    """``selected`` with each successful receipt promoted over its step's entry.

    A failed receipt is history and nothing else: it is recorded, and it leaves
    whatever was selected for that step exactly where it was.
    """
    promoted = {receipt_step_key(item): item for item in recorded if item.status == "succeeded"}
    kept = [item for item in selected if receipt_step_key(item) not in promoted]
    return tuple(sorted((*kept, *promoted.values()), key=receipt_step_key))


def record_evaluation(
    ree: Ree,
    *,
    dependency_level: int,
    environment_level: int,
    machine_level: int,
    detected_dependencies: str,
) -> EvidenceTransition:
    state = record_state_evaluation(
        ree.evidence.state,
        dependency_level=dependency_level,
        environment_level=environment_level,
        machine_level=machine_level,
        detected_dependencies=detected_dependencies,
    )
    evidence = ree.evidence.model_copy(update={"state": state})
    updated = ree.model_copy(update={"evidence": evidence})
    return EvidenceTransition(
        before_revision=revision_of(ree),
        after_revision=revision_of(updated),
        authored=ree.authored,
        evidence=evidence,
    )


def prepare_publication(
    ree: Ree,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
) -> PublicationTransition:
    state = select_packaging(
        ree.evidence.state,
        source_included=source_included,
        runtime_included=runtime_included,
        results_included=results_included,
    )
    return PublicationTransition(revision=revision_of(ree), state=state)


def record_seal(
    ree: Ree,
    *,
    sealed_at: UtcInstant,
    seal_hash: Digest,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
) -> PublicationTransition:
    state = record_state_seal(
        ree.evidence.state,
        sealed_at=sealed_at,
        seal_hash=seal_hash,
        source_included=source_included,
        runtime_included=runtime_included,
        results_included=results_included,
    )
    publication = SealedRee(
        seal_hash=seal_hash,
        sealed_at=sealed_at,
        source_included=source_included,
        runtime_included=runtime_included,
        results_included=results_included,
    )
    return PublicationTransition(revision=revision_of(ree), state=state, publication=publication)
