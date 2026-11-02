"""The stores an operator registered, and the tokens their workbenches present.

A store is a directory of REEs on some machine. The workbench serving it dials in with a
token minted for that store alone, so a token never admits a workbench to another store,
and revoking it shuts that workbench out. Only token digests are kept, in a file readable
by its owner only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_supervisor.json_file import write_json_atomic

# A store id names a store in URLs and on the command line: one plain segment.
_STORE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
# How much of a token its owner sees again, to name it when revoking.
TOKEN_PREFIX_LENGTH = 8


class StoreRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    store_id: str
    label: str = ""
    created_at: str


class TokenRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prefix: str = Field(min_length=TOKEN_PREFIX_LENGTH, max_length=TOKEN_PREFIX_LENGTH)
    digest: str
    store_id: str
    created_at: str
    revoked_at: str | None = None


class UnknownStoreError(LookupError):
    pass


class StoreRegistry:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def add(self, store_id: str, label: str = "") -> StoreRecord:
        if not _STORE_ID.fullmatch(store_id):
            raise ValueError(f"not a store id: {store_id!r}")
        with self._lock:
            stores, tokens = self._read()
            if store_id in stores:
                raise ValueError(f"store {store_id!r} is already registered")
            record = StoreRecord(store_id=store_id, label=label, created_at=_now())
            stores[store_id] = record
            self._write(stores, tokens)
            return record

    def get(self, store_id: str) -> StoreRecord | None:
        with self._lock:
            return self._read()[0].get(store_id)

    def all(self) -> list[StoreRecord]:
        with self._lock:
            return sorted(self._read()[0].values(), key=lambda record: record.store_id)

    def mint_token(self, store_id: str) -> str:
        """A new token admitting a workbench to ``store_id``; shown once, kept only as a digest."""
        with self._lock:
            stores, tokens = self._read()
            if store_id not in stores:
                raise UnknownStoreError(store_id)
            token = secrets.token_urlsafe(32)
            tokens.append(
                TokenRecord(
                    prefix=token[:TOKEN_PREFIX_LENGTH], digest=_digest(token), store_id=store_id, created_at=_now()
                )
            )
            self._write(stores, tokens)
            return token

    def authenticate(self, token: str, store_id: str) -> bool:
        """Whether ``token`` was minted for ``store_id`` and is not revoked."""
        if not token:
            return False
        digest = _digest(token)
        with self._lock:
            stores, tokens = self._read()
        return store_id in stores and any(
            record.store_id == store_id and record.revoked_at is None and hmac.compare_digest(record.digest, digest)
            for record in tokens
        )

    def revoke(self, prefix: str) -> int:
        """Revoke every live token starting with ``prefix``; how many."""
        with self._lock:
            stores, tokens = self._read()
            revoked = 0
            for index, record in enumerate(tokens):
                if record.prefix == prefix and record.revoked_at is None:
                    tokens[index] = record.model_copy(update={"revoked_at": _now()})
                    revoked += 1
            if revoked:
                self._write(stores, tokens)
            return revoked

    def _read(self) -> tuple[dict[str, StoreRecord], list[TokenRecord]]:
        if not self._path.exists():
            return {}, []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        stores = {key: StoreRecord.model_validate(value) for key, value in raw.get("stores", {}).items()}
        tokens = [TokenRecord.model_validate(value) for value in raw.get("tokens", [])]
        return stores, tokens

    def _write(self, stores: dict[str, StoreRecord], tokens: list[TokenRecord]) -> None:
        write_json_atomic(
            self._path,
            {
                "stores": {key: record.model_dump(mode="json") for key, record in stores.items()},
                "tokens": [record.model_dump(mode="json") for record in tokens],
            },
        )


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
