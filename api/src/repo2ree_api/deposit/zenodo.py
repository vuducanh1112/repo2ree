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
    archive = "zenodo"

    @property
    def capabilities(self) -> DepositCapabilities:
        return DepositCapabilities(
            archive="zenodo",
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
        raise NotImplementedError("Zenodo draft creation not wired up yet")

    def publish(self, record: DepositRecord) -> ArchiveBindingAttestation:
        raise NotImplementedError("Zenodo publish not wired up yet")
