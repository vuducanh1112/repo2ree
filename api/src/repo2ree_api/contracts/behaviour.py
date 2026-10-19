"""Behaviour evidence as the control plane serves it to collectors.

Journals and persisted owner state are served as written, not re-modelled: the
checker that judges them must see what the owners recorded, so these models
only frame the documents and say when they were read.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BehaviourJournal(BaseModel):
    id: str = Field(description="`<process>-<epoch>`, the journal's file name without its extension.")
    process: str
    epoch: int
    last_seq: int = Field(description="The highest sequence number among its complete records.")


class BehaviourJournalList(BaseModel):
    journals: list[BehaviourJournal]


class BehaviourPositions(BaseModel):
    positions: dict[str, int] = Field(description="Each journal's highest complete sequence number, by journal id.")


class BehaviourState(BaseModel):
    """The owners' persisted state, read between two sets of journal positions."""

    cut: dict[str, tuple[int, int]] = Field(
        description="Per journal id: the last sequence number read before the stores, and the last read after."
    )
    runs: dict[str, dict[str, Any]] = Field(description="Each run's persisted `state.json`, by run directory name.")
    allocations: dict[str, Any] | None = Field(description="The allocation store's persisted document, if any.")


class BehaviourArchive(BaseModel):
    """One REE archive the control plane served, so a collector can place the copy a client kept."""

    ree_id: str
    sha256: str = Field(description="Digest of the archive bytes as served; identifies the client's copy.")
    size: int
    cut: dict[str, tuple[int, int]] = Field(
        description="Per journal id: the last sequence number read before building the archive, and after."
    )


class BehaviourArchiveList(BaseModel):
    archives: list[BehaviourArchive]
