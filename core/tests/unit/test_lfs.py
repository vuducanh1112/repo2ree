"""LFS pointers stay small while offline payloads retain their exact identity."""

import hashlib
import subprocess

import pytest

from repo2ree_core.persistence.lfs import LfsPointer, store_payload
from repo2ree_core.tooling import find_tool
from repo2ree_ree.digest import digest_json
from repo2ree_ree.model import ReeSubject, canonical_subject_digest


def test_legacy_subject_digest_is_unchanged():
    subject = ReeSubject()
    original = subject.model_dump(mode="json", exclude={"capture"})
    assert canonical_subject_digest(subject) == digest_json(
        {"domain": "org.repo2ree.ree-subject", "version": 1, "subject": original}
    )


def test_pointer_matches_git_lfs_and_verifies_payload(tmp_path):
    source = tmp_path / "runtime"
    source.write_bytes(b"runtime\0" * 4096)
    git_dir = tmp_path / ".git"
    pointer = store_payload(source, git_dir)
    assert pointer.oid == hashlib.sha256(source.read_bytes()).hexdigest()
    assert pointer.size == source.stat().st_size
    assert len(pointer.encode()) < 200
    assert LfsPointer.parse(pointer.encode()) == pointer
    executable = find_tool("git-lfs")
    assert executable is not None, "Git LFS is required for compatibility validation"
    result = subprocess.run([executable, "pointer", "--file", str(source)], check=True, capture_output=True)
    assert result.stdout == pointer.encode()
    assert store_payload(source, git_dir) == pointer
    pointer.object_path(git_dir).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Corrupt LFS"):
        pointer.verify(git_dir)


def test_interrupted_payload_never_publishes_object(tmp_path):
    source = tmp_path / "runtime"
    source.write_bytes(b"x" * (2 * 1024 * 1024))

    def interrupt(_size):
        raise RuntimeError("interrupted")

    with pytest.raises(RuntimeError, match="interrupted"):
        store_payload(source, tmp_path / ".git", on_chunk=interrupt)
    assert not (tmp_path / ".git/lfs/objects").exists()
    assert not list((tmp_path / ".git/lfs/tmp").iterdir())
