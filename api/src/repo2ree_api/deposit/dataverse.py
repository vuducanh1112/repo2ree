"""Dataverse — deposits the sealed bundle into an institutional installation.

Differs from Zenodo in one way that shapes the whole adapter: there is no single
Dataverse. Every installation is a separate host with its own token, its own
collections, and its own DOI/Handle prefix, so ``server`` is a required
parameter rather than a constant and a token is only ever valid for the
installation it came from.

Otherwise the lifecycle matches: a dataset is created as a draft, files are
uploaded into it, and publishing is the irreversible step that fixes the
persistent identifier. Dataverse assigns that identifier at draft creation
rather than at publish, so the pre-reservation route is available here too, with
the same trade-off — it means touching the archive before sealing.
"""

from __future__ import annotations

from repo2ree_api.deposit.models import (
    ArchiveBindingAttestation,
    ArchivePresenceObservation,
    DepositCapabilities,
    DepositRecord,
    DepositRequest,
)

# No default host on purpose: depositing to the wrong installation is not
# recoverable, so the caller names one. The client-side catalog suggests
# Harvard's as a starting point.
DATAVERSE_REQUIRED_PARAMS = ("server", "dataverse")


class DataverseAdapter:
    """Bundle deposit against a caller-named Dataverse installation."""

    archive = "dataverse"

    @property
    def capabilities(self) -> DepositCapabilities:
        return DepositCapabilities(
            archive="dataverse",
            supports_presence_lookup=False,
            supports_bundle_deposit=True,
            requires_origin_url=False,
            # Self-service on public installations; institutional ones may gate
            # who can create datasets, which is a per-installation policy rather
            # than a property of Dataverse.
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
        """Create the draft dataset and upload the sealed bundle into it."""
        raise NotImplementedError("Dataverse draft creation not wired up yet")

    def publish(self, record: DepositRecord) -> ArchiveBindingAttestation:
        """Publish the dataset, fixing its persistent identifier. Irreversible."""
        raise NotImplementedError("Dataverse publish not wired up yet")
