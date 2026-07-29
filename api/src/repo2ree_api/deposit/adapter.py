"""The seam every archive adapter implements.

What the three archives share is a *lifecycle* — check, draft, upload, publish,
record — not an API. Their auth models, payload shapes, versioning semantics and
identifier namespaces differ enough that a common "provider API" would leak
immediately, so this protocol unifies only the lifecycle and lets each adapter
own its own wire format.

Deposit is deliberately not one call. ``create_draft`` is reversible and
``publish`` is not: a published DOI cannot be withdrawn, so the split is the
safety mechanism, not an artifact of Zenodo's data model.

Adapters run in the control plane — the API service — and nowhere else. They hold user
credentials, and the workbench executes the author's own code — a deposit token
must never be reachable from there. The agent is likewise out of scope: it
already holds the Docker socket, and widening it to carry user archive
credentials would compound that.
"""

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
    """The adapter cannot perform this step — a fact about the archive.

    Not a "todo": Software Heritage genuinely cannot accept an uploaded bundle
    without institutional deposit credentials. Callers should surface the
    ``DepositCapabilities`` reason rather than treating it as a transient
    failure.
    """


@runtime_checkable
class DepositAdapter(Protocol):
    """One archive, across the deposit lifecycle."""

    @property
    def capabilities(self) -> DepositCapabilities:
        """What this archive can actually do; drives what the UI may offer."""
        ...

    def check_presence(self, subject: str) -> ArchivePresenceObservation:
        """Ask whether the archive already holds ``subject``.

        A read: idempotent, no credentials, safe to call speculatively. The
        answer is a point-in-time observation, not a property of the REE.
        """
        ...

    def create_draft(self, request: DepositRequest) -> DepositRecord:
        """Open a reversible deposit and upload the sealed bundle to it."""
        ...

    def publish(self, record: DepositRecord) -> ArchiveBindingAttestation:
        """Make the draft permanent and return the binding it produced.

        Irreversible. Must never run as a side effect of another operation.
        """
        ...
