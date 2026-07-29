"""Zenodo — deposits the sealed bundle and issues a citable DOI.

The one archive here that does what the archive page promises: upload bytes,
get a DOI. Three things shape the adapter.

**Draft then publish.** Zenodo depositions start unpublished and can be
discarded. Publishing is final — a Zenodo DOI cannot be withdrawn — so the two
steps stay two steps, and ``publish`` only ever runs from an explicit user
request.

**Pre-reservation.** A draft can reserve its DOI before publishing, which is the
*only* sound way to get a DOI inside the seal: reserve, write it into the
manifest, seal, upload, publish. The cost is that it inverts "seal, then
deposit" — you touch the archive before sealing, and a re-seal strands the
reserved DOI. Default to recording an attestation afterwards instead; treat
pre-reservation as opt-in.

**Versioning.** A record has a stable concept DOI plus a per-version DOI. Both
belong on the attestation: the concept DOI is what a paper should cite, the
version DOI is what names these exact bytes.
"""

from __future__ import annotations

from repo2ree_api.deposit.models import (
    ArchiveBindingAttestation,
    ArchivePresenceObservation,
    DepositCapabilities,
    DepositRecord,
    DepositRequest,
)

ZENODO_API_ROOT = "https://zenodo.org/api"
ZENODO_SANDBOX_API_ROOT = "https://sandbox.zenodo.org/api"


class ZenodoAdapter:
    """Bundle deposit against Zenodo's deposition API."""

    archive = "zenodo"

    @property
    def capabilities(self) -> DepositCapabilities:
        return DepositCapabilities(
            archive="zenodo",
            # Zenodo indexes by its own record ids, not by content digest, so
            # there is no content-addressed "do you already have this?" query.
            supports_presence_lookup=False,
            supports_bundle_deposit=True,
            requires_origin_url=False,
            requires_institutional_credentials=False,
            supports_identifier_prereservation=True,
            notes="Personal API token. Publishing is irreversible; drafts can be discarded.",
        )

    def check_presence(self, subject: str) -> ArchivePresenceObservation:
        return ArchivePresenceObservation(
            archive="zenodo",
            subject=subject,
            presence="not_checked",
        )

    def create_draft(self, request: DepositRequest) -> DepositRecord:
        """Open an unpublished deposition and upload the sealed bundle to it.

        The bundle is read from control-plane storage and uploaded byte for
        byte. It must not be repacked on the way out: its sha256 *is* the
        ``ree_digest`` the attestation will bind, so any re-zip would break the
        identity the DOI is about to name.
        """
        raise NotImplementedError("Zenodo draft creation not wired up yet")

    def publish(self, record: DepositRecord) -> ArchiveBindingAttestation:
        """Publish the draft and mint the DOI. Irreversible.

        Must be idempotent against ``record.idempotency_key``: a retry after a
        timeout that publishes twice mints a second DOI for the same bundle, and
        neither can be withdrawn.
        """
        raise NotImplementedError("Zenodo publish not wired up yet")
