"""Pure REE transitions: immutable values in, explicit decisions out."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

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
from repo2ree_core.domain.ree.model import (
    AuthoredFile,
    Ree,
    ReeDefinition,
    ReeEvidence,
    SealedRee,
)
from repo2ree_core.domain.ree.state import (
    ReeLifecycleState,
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
    payload = {
        "intent": ree.authored.intent.model_dump(mode="json"),
        "files": [file.model_dump(mode="json") for file in ree.authored.files],
        "source_snapshot_digest": ree.evidence.state.source_snapshot_digest,
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


def record_source_acquisition(
    ree: Ree,
    *,
    acquired_by: Literal["download", "upload"],
    captured_at: UtcInstant,
    snapshot_archive: ReePath,
    origin_url: str = "",
    source_type: str = "",
    resolved_commit: GitRevision | None = None,
    uploaded_archive: ReePath | None = None,
    swhid: Swhid | None = None,
) -> EvidenceTransition:
    patch: dict[str, Any] = {}
    if acquired_by == "download":
        patch.update(origin_url=origin_url, source_type=source_type)
        if resolved_commit:
            patch["revision"] = resolved_commit
    if swhid:
        patch["swhid"] = swhid
    authored = _patch_definition(ree.authored, patch) if patch else ree.authored
    state = record_source(
        ree.evidence.state,
        acquired_by=acquired_by,
        archive_name=uploaded_archive,
        snapshot_archive=snapshot_archive,
        snapshot_captured_at=captured_at,
        resolved_commit=resolved_commit,
    )
    evidence = ree.evidence.model_copy(update={"state": state})
    updated = ree.model_copy(update={"authored": authored, "evidence": evidence})
    return EvidenceTransition(
        before_revision=revision_of(ree),
        after_revision=revision_of(updated),
        authored=authored,
        evidence=evidence,
    )


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
