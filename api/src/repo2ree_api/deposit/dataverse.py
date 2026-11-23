from __future__ import annotations

from repo2ree_api.deposit.models import (
    ArchiveBindingAttestation,
    ArchivePresenceObservation,
    DepositCapabilities,
    DepositRecord,
    DepositRequest,
)

DATAVERSE_REQUIRED_PARAMS = ("server", "dataverse")


class DataverseAdapter:
    archive = "dataverse"

    @property
    def capabilities(self) -> DepositCapabilities:
        return DepositCapabilities(
            archive="dataverse",
            supports_presence_lookup=False,
            supports_bundle_deposit=True,
            requires_origin_url=False,
            requires_institutional_credentials=False,
            supports_identifier_prereservation=True,
            notes=(
                "Per-installation host and token; 'server' and 'dataverse' are required "
                "params. Publishing is irreversible."
            ),
        )

    def check_presence(self, subject: str) -> ArchivePresenceObservation:
        return ArchivePresenceObservation(
            archive="dataverse",
            subject=subject,
            presence="not_checked",
        )

    def create_draft(self, request: DepositRequest) -> DepositRecord:
        raise NotImplementedError("Dataverse draft creation not wired up yet")

    def publish(self, record: DepositRecord) -> ArchiveBindingAttestation:
        raise NotImplementedError("Dataverse publish not wired up yet")
