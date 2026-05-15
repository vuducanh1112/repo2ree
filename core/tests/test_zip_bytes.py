import io
import zipfile

from repo2ree_core.workspace.bundle import build_zip_bytes


def _unzip(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {info.filename: zf.read(info.filename) for info in zf.infolist()}


def test_empty_entries_produces_valid_empty_zip():
    data = build_zip_bytes([])
    assert _unzip(data) == {}


def test_entries_written_at_their_paths():
    data = build_zip_bytes(
        [
            ("ree/ree.json", b'{"name":"demo"}'),
            ("ree/runtime", b"\x00\x01\x02tarball"),
        ]
    )
    assert _unzip(data) == {
        "ree/ree.json": b'{"name":"demo"}',
        "ree/runtime": b"\x00\x01\x02tarball",
    }


def test_preserves_input_order_for_duplicates():
    # Duplicates are caller's responsibility; consumer keeps the last
    # write when reading by name, but the zip records both entries.
    data = build_zip_bytes([("dup", b"first"), ("dup", b"second")])
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [info.filename for info in zf.infolist()]
    assert names == ["dup", "dup"]


def test_uses_deflate_compression():
    payload = b"a" * 10_000  # highly compressible
    data = build_zip_bytes([("payload", payload)])
    # The compressed archive should be much smaller than the raw payload
    assert len(data) < len(payload) // 2
    assert _unzip(data) == {"payload": payload}


def test_handles_binary_content():
    raw = bytes(range(256))
    data = build_zip_bytes([("binary", raw)])
    assert _unzip(data) == {"binary": raw}


def test_iterator_input_is_consumed_once():
    def gen():
        yield ("a", b"1")
        yield ("b", b"2")

    data = build_zip_bytes(gen())
    assert _unzip(data) == {"a": b"1", "b": b"2"}
