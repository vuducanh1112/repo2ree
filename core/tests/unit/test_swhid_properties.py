"""Property-based checks for the pure SWHID hashing core.

The example-based oracle tests (git ``hash-object``/``write-tree`` parity) live
in ``test_swhid.py``; this file asserts the *invariants* that hold for every
input, which is where the subtle ordering bugs hide. Whole file is one kind, so
the marker is applied at module level.
"""

from __future__ import annotations

import subprocess

import pytest
from hypothesis import given
from hypothesis import strategies as st

from repo2ree_core.source_repo import content_swhid
from repo2ree_core.source_repo.swhid import (
    _MODE_DIR,
    _MODE_EXEC,
    _MODE_FILE,
    _MODE_SYMLINK,
    _TreeEntry,
    content_object_id,
    hash_directory_entries,
)

pytestmark = pytest.mark.property

_MODES = st.sampled_from([_MODE_FILE, _MODE_EXEC, _MODE_SYMLINK, _MODE_DIR])


@st.composite
def _tree_entries(draw: st.DrawFn) -> list[_TreeEntry]:
    """A directory's worth of entries with distinct names (git requires it)."""
    names = draw(
        st.lists(
            st.binary(min_size=1, max_size=8).filter(lambda b: b"/" not in b and b"\x00" not in b),
            min_size=0,
            max_size=6,
            unique=True,
        )
    )
    return [
        _TreeEntry(mode=draw(_MODES), name=name, object_id=draw(st.binary(min_size=20, max_size=20))) for name in names
    ]


class TestContentObjectId:
    @given(st.binary(max_size=512))
    def test_deterministic(self, data: bytes) -> None:
        """Same bytes always hash to the same id."""
        assert content_object_id(data) == content_object_id(data)

    @given(st.binary(max_size=512))
    def test_matches_git_hash_object(self, data: bytes) -> None:
        """The blob id is git's own ``hash-object`` for the same bytes."""
        expected = (
            subprocess.run(
                ["git", "hash-object", "--stdin"],
                input=data,
                check=True,
                capture_output=True,
            )
            .stdout.decode()
            .strip()
        )
        assert content_object_id(data).hex() == expected

    @given(st.binary(max_size=512))
    def test_swhid_wraps_object_id(self, data: bytes) -> None:
        assert content_swhid(data) == f"swh:1:cnt:{content_object_id(data).hex()}"


class TestHashDirectoryEntries:
    @given(_tree_entries())
    def test_order_independent(self, entries: list[_TreeEntry]) -> None:
        """The tree id is independent of the order entries are supplied in.

        ``hash_directory_entries`` sorts internally (git orders by name, dirs as
        ``name + "/"``), so any permutation of the same set must hash equal —
        the invariant a shuffled-input property test is built to defend.
        """
        assert hash_directory_entries(list(reversed(entries))) == hash_directory_entries(entries)

    @given(_tree_entries())
    def test_deterministic(self, entries: list[_TreeEntry]) -> None:
        assert hash_directory_entries(entries) == hash_directory_entries(entries)

    @given(_tree_entries(), st.binary(min_size=1, max_size=8), st.binary(min_size=20, max_size=20))
    def test_adding_a_new_entry_changes_the_hash(
        self, entries: list[_TreeEntry], name: bytes, object_id: bytes
    ) -> None:
        """Distinct entry sets hash distinctly (no accidental collisions)."""
        if b"/" in name or b"\x00" in name or any(e.name == name for e in entries):
            return  # name would collide with an existing entry; not a new set
        extra = _TreeEntry(mode=_MODE_FILE, name=name, object_id=object_id)
        assert hash_directory_entries([*entries, extra]) != hash_directory_entries(entries)
