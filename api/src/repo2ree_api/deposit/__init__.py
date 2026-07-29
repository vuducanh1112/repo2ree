"""Depositing a sealed REE into an external archive, and recording what came back.

Runs in the control plane — the API service, never the workbench or the agent —
for three reasons, each sufficient on its own:

* **Credentials.** Deposit needs a user's archive token. The workbench runs the
  author's own build and experiment scripts, so a token there is exfiltrable by
  design; the agent already holds the Docker socket and should not also hold
  user credentials.
* **Payload.** The thing deposited is the sealed bundle, which the control plane
  already stores. Depositing from anywhere else means pushing those bytes out
  through a second path.
* **Irreversibility.** A published DOI cannot be withdrawn, so deposit must be
  explicitly user-initiated — never a side effect of an authoring run.

What comes back is an :class:`ArchiveBindingAttestation`, stored *beside* the
sealed bundle rather than written into it: the bundle is frozen at seal time,
and mutating it to add a DOI would change the very digest the DOI was issued
for. See ``docs/research/sealing.md``.
"""

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
