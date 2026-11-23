from __future__ import annotations

from repo2ree_api.deposit.adapter import DepositAdapter
from repo2ree_api.deposit.dataverse import DataverseAdapter
from repo2ree_api.deposit.models import ArchiveProvider, DepositCapabilities
from repo2ree_api.deposit.software_heritage import SoftwareHeritageAdapter
from repo2ree_api.deposit.zenodo import ZenodoAdapter

_ADAPTERS: dict[str, DepositAdapter] = {
    "software_heritage": SoftwareHeritageAdapter(),
    "zenodo": ZenodoAdapter(),
    "dataverse": DataverseAdapter(),
}


def deposit_adapter(archive: ArchiveProvider) -> DepositAdapter:
    return _ADAPTERS[archive]


def deposit_capabilities() -> list[DepositCapabilities]:
    return [adapter.capabilities for adapter in _ADAPTERS.values()]
