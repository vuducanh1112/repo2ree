"""The vocabulary of depositing a sealed REE into an external archive.

A deposit identifier (DOI, PID, SWHID) is *not* a property of an REE. It names
a **deposit event**: some archive accepted a bundle with a given ``ree_digest``
at a given time and issued an identifier for it. One sealed REE can be
deposited to several archives, and re-deposited as new versions, so the record
is an append-only set of typed claims rather than a field on the intent.

That claim is an ``archive_binding`` attestation, in the envelope shape
``docs/research/sealing.md`` specifies:

    DOI/PID X resolves to a deposit that contains or references ree_digest Y.

Note the direction — the attestation points at the digest, never the reverse.
The sealed bundle is immutable, so nothing learned after sealing can be written
back into it; attestations live *beside* the bundle instead.

Pure module: models and vocabulary only, no I/O.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ================================================
# Types
# ================================================

# The archives repo2ree knows how to talk to. Not interchangeable: Software
# Heritage archives *source code* reached by URL, while Zenodo and Dataverse
# accept *deposited bytes* and issue citable DOIs.
ArchiveProvider = Literal["software_heritage", "zenodo", "dataverse"]

# Where a deposit has got to. ``draft`` is the reversible step that exists so a
# user can inspect before the irreversible one: a published DOI cannot be
# withdrawn, so nothing reaches ``published`` without an explicit request.
DepositState = Literal["pending", "draft", "published", "failed"]

# Whether an archive is *known to hold* the content, which is a different
# question from whether we deposited it. Deliberately tri-state: a binary flag
# renders "not archived" when the truth is "we could not reach the archive".
ArchivePresence = Literal["known", "unknown", "not_checked"]


# ================================================
# Data Models
# ================================================


class ArchiveBindingAttestation(BaseModel):
    """One claim: an archive's deposit holds the REE with this content digest.

    Stored beside the sealed bundle and indexed by the control plane; never
    written into the bundle, which is frozen at seal time. ``signature`` and
    ``verification_material`` are optional because an unsigned binding is still
    a useful record — signing makes it *checkable* by a third party rather than
    merely asserted, and can be added later without rewriting anything.
    """

    model_config = ConfigDict(extra="forbid")

    # The sealed REE this claim is about. The join key for everything here.
    subject_digest: str
    claim_type: Literal["archive_binding"] = "archive_binding"
    signer_identity: str = ""
    signer_role: str = "archive_adapter"
    signed_at: str = ""
    policy: str = ""
    signature: str | None = None
    verification_material: str | None = None

    # ── the binding itself ──
    archive: ArchiveProvider
    # The identifier the archive issued, in its own namespace: "doi:10.5281/…",
    # "swh:1:dir:…", "hdl:1902.1/…".
    identifier: str
    record_url: str = ""
    # Archives version deposits under a stable concept identifier (Zenodo's
    # concept DOI, Dataverse's dataset PID). Empty when the archive has no such
    # notion or the deposit is unversioned.
    concept_identifier: str = ""
    version: str = ""


class DepositRecord(BaseModel):
    """The control plane's view of one deposit attempt, across its lifecycle.

    Distinct from the attestation: this is mutable working state (a draft that
    has not been published yet, a failure to retry), whereas the attestation is
    the settled, append-only fact produced once an identifier exists.
    """

    model_config = ConfigDict(extra="forbid")

    deposit_id: str
    ree_id: str
    subject_digest: str
    archive: ArchiveProvider
    state: DepositState = "pending"
    # Echoed back so a retry cannot mint a second DOI for the same bundle —
    # the one failure mode in this area that cannot be undone.
    idempotency_key: str | None = None
    attestation: ArchiveBindingAttestation | None = None
    error: str = ""
    created_at: str = ""
    updated_at: str = ""


class ArchivePresenceObservation(BaseModel):
    """ "Does this archive already hold this content?" — asked at a point in time.

    Unlike a digest, this is a *mutable fact about the outside world*: it only
    ever flips ``unknown`` → ``known`` as archives crawl, so it carries the time
    it was asked and must never be sealed as a settled property of the REE.
    """

    model_config = ConfigDict(extra="forbid")

    archive: ArchiveProvider
    # What was looked up — for Software Heritage, a SWHID.
    subject: str
    presence: ArchivePresence = "not_checked"
    checked_at: str = ""
    # Present only when ``presence == "known"``.
    record_url: str = ""


class DepositCapabilities(BaseModel):
    """What an adapter can actually do, so the UI can stop promising more.

    Every field here is ``False`` for at least one provider, which is the point:
    Software Heritage cannot accept uploaded bytes without institutional
    credentials, and its Save Code Now path needs a public origin URL rather
    than a bundle.
    """

    model_config = ConfigDict(extra="forbid")

    archive: ArchiveProvider
    # Can we ask whether the archive already holds this content?
    supports_presence_lookup: bool = False
    # Can we upload the sealed bundle itself?
    supports_bundle_deposit: bool = False
    # Does depositing need a public origin URL rather than bytes?
    requires_origin_url: bool = False
    # Does it need credentials the user cannot self-serve?
    requires_institutional_credentials: bool = False
    # Can an identifier be reserved before publishing, so it can be sealed in?
    supports_identifier_prereservation: bool = False
    notes: str = ""


class DepositRequest(BaseModel):
    """What a caller must supply to start a deposit."""

    model_config = ConfigDict(extra="forbid")

    ree_id: str
    subject_digest: str
    # Provider-specific options — Zenodo access level, Dataverse server and
    # collection, Software Heritage visit type. Left untyped at this seam so
    # each adapter validates its own; see ARCHIVE_REPOSITORIES on the client.
    params: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str | None = None
