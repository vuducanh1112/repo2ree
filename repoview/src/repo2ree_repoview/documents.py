"""The two kinds of JSON document the views handle: those others write, and those the views write."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Document(BaseModel):
    """A document another part of the repository writes, read for the fields a view draws."""

    model_config = ConfigDict(frozen=True, extra="ignore")


class Record(BaseModel):
    """A document the views write themselves, so nothing in it goes unaccounted for."""

    model_config = ConfigDict(frozen=True, extra="forbid")
