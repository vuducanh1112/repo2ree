from __future__ import annotations

from typing import Protocol, runtime_checkable

from repo2ree_api.deposit.models import (
    ArchiveBindingAttestation,
    ArchivePresenceObservation,
    DepositCapabilities,
    DepositRecord,
    DepositRequest,
)


class DepositNotSupportedError(NotImplementedError):
    pass


@runtime_checkable
class DepositAdapter(Protocol):
    @property
    def capabilities(self) -> DepositCapabilities: ...

    def check_presence(self, subject: str) -> ArchivePresenceObservation: ...

    def create_draft(self, request: DepositRequest) -> DepositRecord: ...

    def publish(self, record: DepositRecord) -> ArchiveBindingAttestation: ...
