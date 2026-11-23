from __future__ import annotations

from repo2ree_api.deposit.adapter import DepositNotSupportedError
from repo2ree_api.deposit.models import (
    ArchiveBindingAttestation,
    ArchivePresenceObservation,
    DepositCapabilities,
    DepositRecord,
    DepositRequest,
)

SWH_API_ROOT = "https://archive.softwareheritage.org/api/1"

SWH_KNOWN_ENDPOINT = f"{SWH_API_ROOT}/known/"
SWH_KNOWN_BATCH_LIMIT = 1000


class SoftwareHeritageAdapter:
    archive = "software_heritage"

    @property
    def capabilities(self) -> DepositCapabilities:
        return DepositCapabilities(
            archive="software_heritage",
            supports_presence_lookup=True,
            supports_bundle_deposit=False,
            requires_origin_url=True,
            requires_institutional_credentials=True,
            supports_identifier_prereservation=False,
            notes=(
                "Archives source reached by URL, not uploaded bytes. Presence lookup is "
                "open; deposit needs SWORD credentials granted per organisation."
            ),
        )

    def check_presence(self, subject: str) -> ArchivePresenceObservation:
        raise NotImplementedError("SWH presence lookup not wired up yet")

    def create_draft(self, request: DepositRequest) -> DepositRecord:
        raise DepositNotSupportedError(
            "Software Heritage does not accept uploaded bundles; its deposit API requires "
            "institutional SWORD credentials"
        )

    def publish(self, record: DepositRecord) -> ArchiveBindingAttestation:
        raise DepositNotSupportedError(
            "Software Heritage does not accept uploaded bundles; its deposit API requires "
            "institutional SWORD credentials"
        )
