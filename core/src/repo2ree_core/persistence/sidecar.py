from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.state import ReeLifecycleState

ReeStatus = Literal["draft", "ready", "sealed", "archived"]


class ReeSidecar(BaseModel):
    """The persisted REE control record stored in ``.ree.json``."""

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
    def _backfill_intent_identity(self) -> ReeSidecar:
        # The sidecar's identity fields (name, external_ref) are always derived
        # from the intent at every write site, but a sidecar can exist before
        # the author fills the intent in — fall back to the identity fields so
        # the intent is never blanker than the REE it describes.
        if not self.ree_intent.name:
            self.ree_intent.name = self.name
        if not self.ree_intent.origin_url and self.external_ref:
            self.ree_intent.origin_url = self.external_ref
        return self

    def with_intent(self, intent: ReeIntent, *, at: str) -> ReeSidecar:
        """This sidecar carrying a new intent, with its identity fields re-derived.

        ``name`` and ``external_ref`` are projections of the intent, not
        independent state — the validator above already assumes so in the other
        direction. Deriving them here rather than at each write site keeps that
        assumption owned by the model that makes it: a store only persists what
        this returns, and cannot invent a sidecar whose name disagrees with the
        intent it holds. Re-validated on the way out, so the round trip either
        yields a sound sidecar or raises before anything reaches disk.
        """
        return self._revalidated(
            ree_intent=intent.model_dump(exclude_none=True),
            name=intent.name or self.name,
            external_ref=intent.origin_url or None,
            updated_at=at,
        )

    def with_state(self, state: ReeLifecycleState, *, at: str) -> ReeSidecar:
        """This sidecar carrying new durable state. Nothing else is derived from it."""
        return self._revalidated(ree_state=state.model_dump(mode="json", exclude_none=True), updated_at=at)

    def _revalidated(self, **changes: object) -> ReeSidecar:
        return ReeSidecar.model_validate(self.model_dump(mode="json", exclude_none=True) | changes)
