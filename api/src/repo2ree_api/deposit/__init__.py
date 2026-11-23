from repo2ree_api.deposit.adapter import DepositAdapter, DepositNotSupportedError
from repo2ree_api.deposit.dataverse import DataverseAdapter
from repo2ree_api.deposit.models import (
    ArchiveBindingAttestation,
    ArchivePresence,
    ArchivePresenceObservation,
    ArchiveProvider,
    DepositCapabilities,
    DepositRecord,
    DepositRequest,
    DepositState,
)
from repo2ree_api.deposit.registry import deposit_adapter, deposit_capabilities
from repo2ree_api.deposit.software_heritage import SoftwareHeritageAdapter
from repo2ree_api.deposit.zenodo import ZenodoAdapter

__all__ = [
    "ArchiveBindingAttestation",
    "ArchivePresence",
    "ArchivePresenceObservation",
    "ArchiveProvider",
    "DataverseAdapter",
    "DepositAdapter",
    "DepositCapabilities",
    "DepositNotSupportedError",
    "DepositRecord",
    "DepositRequest",
    "DepositState",
    "SoftwareHeritageAdapter",
    "ZenodoAdapter",
    "deposit_adapter",
    "deposit_capabilities",
]
