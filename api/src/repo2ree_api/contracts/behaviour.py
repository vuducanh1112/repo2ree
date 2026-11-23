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
    cut: dict[str, tuple[int, int]] = Field(
        description="Per journal id: the last sequence number read before the stores, and the last read after."
    )
    runs: dict[str, dict[str, Any]] = Field(description="Each run's persisted `state.json`, by run directory name.")


class BehaviourArchive(BaseModel):
    ree_id: str
    sha256: str = Field(description="Digest of the archive bytes as served; identifies the client's copy.")
    size: int
    cut: dict[str, tuple[int, int]] = Field(
        description="Per journal id: the last sequence number read before building the archive, and after."
    )


class BehaviourArchiveList(BaseModel):
    archives: list[BehaviourArchive]
