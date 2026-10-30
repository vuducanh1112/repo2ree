import asyncio
import hashlib
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from repo2ree_supervisor.transfers import TRANSFER_PATH_PREFIX, TransferError, Transfers


async def body(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


def token_of(path: str) -> str:
    return path.removeprefix(TRANSFER_PATH_PREFIX)


def test_a_transfer_takes_one_upload_and_hands_over_the_file(tmp_path: Path) -> None:
    inbox = Transfers(tmp_path)
    path = inbox.open_upload()

    received = asyncio.run(inbox.receive(token_of(path), body(b"abc", b"def"), 6))
    with pytest.raises(TransferError, match="no such open transfer"):
        asyncio.run(inbox.receive(token_of(path), body(b"again"), 5))

    collected = inbox.collect(path)
    assert collected == received
    assert collected.path.read_bytes() == b"abcdef"
    assert collected.sha256 == hashlib.sha256(b"abcdef").hexdigest()


def test_an_upload_shorter_than_it_announced_is_refused_and_never_collected(tmp_path: Path) -> None:
    inbox = Transfers(tmp_path)
    path = inbox.open_upload()

    with pytest.raises(TransferError, match="ended after 3 of 10 bytes"):
        asyncio.run(inbox.receive(token_of(path), body(b"abc"), 10))
    with pytest.raises(TransferError, match="no complete upload"):
        inbox.collect(path)
    assert list(tmp_path.iterdir()) == []


def test_an_unknown_token_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TransferError, match="no such open transfer"):
        asyncio.run(Transfers(tmp_path).receive("guessed", body(b"x"), 1))


def test_discarding_a_transfer_removes_what_arrived(tmp_path: Path) -> None:
    inbox = Transfers(tmp_path)
    path = inbox.open_upload()
    asyncio.run(inbox.receive(token_of(path), body(b"partial"), None))

    inbox.discard(path)

    assert list(tmp_path.iterdir()) == []


def test_an_offered_file_is_served_once_and_never_deleted(tmp_path: Path) -> None:
    source = tmp_path / "upload.tar.gz"
    source.write_bytes(b"source")
    transfers = Transfers(tmp_path)
    path = transfers.offer(source)

    assert transfers.serve(token_of(path)) == source
    with pytest.raises(TransferError, match="no such open transfer"):
        transfers.serve(token_of(path))
    transfers.close(path)

    assert source.read_bytes() == b"source"
