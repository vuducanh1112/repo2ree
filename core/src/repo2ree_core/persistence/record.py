from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.state import ReeLifecycleState

ReeStatus = Literal["draft", "ready", "sealed", "archived"]


class ReeRecord(BaseModel):
    """The persisted record of one REE, stored in ``.ree.json``.

    Identity, status, and the two head documents (``ree_intent``,
    ``ree_state``) — which is to say, the part of an REE that is not a tree.
    Authored files live in ``overlay/`` and evidence in ``runs/``, and both are
    their own truth; :func:`~repo2ree_core.persistence.repository.load_ree`
    assembles this record and those trees into a whole
    :class:`~repo2ree_core.domain.ree.model.Ree`. Nothing here is derived from
    anything else on disk, which is precisely what earns it a file.

    Deliberately small for a second reason: the catalog lists REEs by reading
    one of these per REE, so anything unbounded added here (the receipt ledger,
    file digests) would be paid on every listing.
    """

    model_config = ConfigDict(extra="forbid")

    ree_id: str
    external_ref: str | None = None
    name: str
    status: ReeStatus = "draft"
    created_at: str
    updated_at: str
    ree_intent: ReeIntent = Field(default_factory=ReeIntent)
    ree_state: ReeLifecycleState = Field(default_factory=ReeLifecycleState)

    @model_validator(mode="after")
    def _backfill_intent_identity(self) -> ReeRecord:
        # The record's identity fields (name, external_ref) are always derived
        # from the intent at every write site, but a record can exist before
        # the author fills the intent in — fall back to the identity fields so
        # the intent is never blanker than the REE it describes.
        if not self.ree_intent.name:
            self.ree_intent.name = self.name
        if not self.ree_intent.origin_url and self.external_ref:
            self.ree_intent.origin_url = self.external_ref
        return self

    def with_intent(self, intent: ReeIntent, *, at: str) -> ReeRecord:
        """This record carrying a new intent, with its identity fields re-derived.

        ``name`` and ``external_ref`` are projections of the intent, not
        independent state — the validator above already assumes so in the other
        direction. Deriving them here rather than at each write site keeps that
        assumption owned by the model that makes it: a store only persists what
        this returns, and cannot invent a record whose name disagrees with the
        intent it holds. Re-validated on the way out, so the round trip either
        yields a sound record or raises before anything reaches disk.
        """
        return self._revalidated(
            ree_intent=intent.model_dump(exclude_none=True),
            name=intent.name or self.name,
            external_ref=intent.origin_url or None,
            updated_at=at,
        )

    def with_state(self, state: ReeLifecycleState, *, at: str) -> ReeRecord:
        """This record carrying new durable state. Nothing else is derived from it."""
        return self._revalidated(ree_state=state.model_dump(mode="json", exclude_none=True), updated_at=at)

    def with_head(
        self,
        intent: ReeIntent,
        state: ReeLifecycleState,
        *,
        at: str,
        status: ReeStatus | None = None,
    ) -> ReeRecord:
        """This record carrying a whole new REE head, in one revalidation.

        The two-in-one counterpart of :meth:`with_intent` and :meth:`with_state`,
        for the saves that settle both. Applying them in sequence would write
        the record twice for one change and leave a window in which the intent
        had moved and the state had not — which is exactly the split the
        repository's single commit exists to close.
        """
        return self._revalidated(
            ree_intent=intent.model_dump(exclude_none=True),
            ree_state=state.model_dump(mode="json", exclude_none=True),
            name=intent.name or self.name,
            external_ref=intent.origin_url or None,
            status=status or self.status,
            updated_at=at,
        )

    def _revalidated(self, **changes: object) -> ReeRecord:
        return ReeRecord.model_validate(self.model_dump(mode="json", exclude_none=True) | changes)
