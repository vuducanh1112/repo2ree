"""The one place that maps a provider name to its adapter.

Kept separate from the adapters so each stays ignorant of the others, and so
callers never construct one by name themselves — an unknown provider must be a
typed failure at one boundary rather than a ``KeyError`` from three call sites.
"""

from __future__ import annotations

from repo2ree_api.control.deposit.adapter import DepositAdapter
from repo2ree_api.control.deposit.dataverse import DataverseAdapter
from repo2ree_api.control.deposit.models import ArchiveProvider, DepositCapabilities
from repo2ree_api.control.deposit.software_heritage import SoftwareHeritageAdapter
from repo2ree_api.control.deposit.zenodo import ZenodoAdapter

_ADAPTERS: dict[str, DepositAdapter] = {
    "software_heritage": SoftwareHeritageAdapter(),
    "zenodo": ZenodoAdapter(),
    "dataverse": DataverseAdapter(),
}


def deposit_adapter(archive: ArchiveProvider) -> DepositAdapter:
    """The adapter for ``archive``.

    Raises ``KeyError`` for an unknown provider — the ``ArchiveProvider`` literal
    means a miss is a programming error, not a client one.
    """
    return _ADAPTERS[archive]


def deposit_capabilities() -> list[DepositCapabilities]:
    """What every known archive can do, for clients deciding what to offer.

    Worth reading before building deposit UI: no two rows are the same, and
    Software Heritage supports none of the bundle-deposit flow at all.
    """
    return [adapter.capabilities for adapter in _ADAPTERS.values()]
