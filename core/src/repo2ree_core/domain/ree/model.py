"""The canonical domain representation of a Reusable Execution Environment.

Open this module to answer "what is an REE?". Persistence is deliberately
elsewhere: a repository hydrates this model from the record, authored tree,
receipt ledger, and seal. Pure functions in ``transitions``,
``assessment``, and ``queries`` interpret and transform these values.

The model separates four kinds of truth:

* ``authored`` — the definition and files an author may change;
* ``evidence`` — immutable receipts plus current durable lifecycle facts;
* ``seal`` — the immutable facts of one seal, absent until the REE is sealed;
* ``assessment`` — capabilities derived from authored inputs and evidence.

``ReeLifecycleState`` contains durable facts produced by operations. It is not a second
author-editable model and handlers must not transition it directly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_core.domain.experiment import Activation
from repo2ree_core.domain.primitives import (
    ArtifactPath,
    Digest,
    GitRevision,
    ReeId,
    ReePath,
    RunId,
    Swhid,
    UtcInstant,
    WorkspacePath,
)
from repo2ree_core.domain.ree.intent import ReeIntent, SourceType
from repo2ree_core.domain.ree.receipt import RunReceipt, receipt_step_key
from repo2ree_core.domain.ree.state import ReeLifecycleState


class _DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ================================================
# Identity and authored definition
# ================================================


class ReeIdentity(_DomainModel):
    ree_id: ReeId
    created_at: UtcInstant
    updated_at: UtcInstant


class AuthoredFile(_DomainModel):
    """Content identity of one file in the authoritative overlay tree."""

    path: ReePath
    digest: Digest
    size: int = Field(ge=0)


class SourceDefinition(_DomainModel):
    origin_url: str = ""
    source_type: SourceType = ""
    revision: GitRevision | None = None
    swhid: Swhid | None = None


class RuntimeDefinition(_DomainModel):
    artifact_path: WorkspacePath | None = None
    activation: Activation = Field(default_factory=Activation)
    sbom_path: ArtifactPath | None = None


class ExperimentScripts(_DomainModel):
    experiment_name: str
    run: AuthoredFile | None = None
    verify: AuthoredFile | None = None


class ReeScripts(_DomainModel):
    """The authored files that have domain meaning as executable recipe."""

    build_runtime: AuthoredFile | None = None
    activation_run: AuthoredFile | None = None
    activation_verify: AuthoredFile | None = None
    experiments: tuple[ExperimentScripts, ...] = ()
    other: tuple[AuthoredFile, ...] = ()


class ReeDefinition(_DomainModel):
    """Everything in the current author-controlled REE head.

    ``intent`` remains the persisted compatibility schema while it is split
    into smaller authored value types. Pure projections expose its domain
    components without duplicating their persisted truth.
    """

    intent: ReeIntent = Field(default_factory=ReeIntent)
    files: tuple[AuthoredFile, ...] = ()

    @model_validator(mode="after")
    def _unique_file_paths(self) -> ReeDefinition:
        paths = [file.path for file in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("authored file paths must be unique")
        return self


# ================================================
# Evidence and seal
# ================================================


class ReeEvidence(_DomainModel):
    """The REE's immutable execution record and selected current evidence.

    ``history`` is append-only. ``selected`` is the deliberate author evidence
    set used for capability assessment; a successful historical run is never
    promoted merely because it exists.
    """

    history: tuple[RunReceipt, ...] = ()
    selected: tuple[RunReceipt, ...] = ()
    state: ReeLifecycleState = Field(default_factory=ReeLifecycleState)

    @model_validator(mode="after")
    def _valid_selected_set(self) -> ReeEvidence:
        keys: set[str] = set()
        for receipt in self.selected:
            if receipt.status != "succeeded":
                raise ValueError("selected evidence must be successful")
            key = receipt_step_key(receipt)
            if key in keys:
                raise ValueError(f"selected evidence contains duplicate step {key!r}")
            keys.add(key)
        return self


class Seal(_DomainModel):
    seal_hash: Digest
    sealed_at: UtcInstant
    source_included: bool = False
    runtime_included: bool = False
    results_included: bool = False


# ================================================
# Derived assessment
# ================================================


CapabilityStatus = Literal["ready", "missing", "stale", "not_applicable"]


class ReeCapability(_DomainModel):
    status: CapabilityStatus
    receipt_run_id: RunId | None = None
    reasons: tuple[str, ...] = ()


class ExperimentCapability(_DomainModel):
    experiment_name: str
    capability: ReeCapability


class ReeAssessment(_DomainModel):
    source: ReeCapability
    runtime: ReeCapability
    activation: ReeCapability
    experiments: tuple[ExperimentCapability, ...] = ()


class Ree(_DomainModel):
    """One hydrated REE value interpreted by the pure domain functions."""

    identity: ReeIdentity
    authored: ReeDefinition
    evidence: ReeEvidence = Field(default_factory=ReeEvidence)
    seal: Seal | None = None
