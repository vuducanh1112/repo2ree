import pytest

from repo2ree_core.workspace.snapshot import (
    snapshot_archive_name,
    strip_archive_suffix,
)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("repo.tar.gz", "repo"),
        ("repo.tgz", "repo"),
        ("repo.zip", "repo"),
        ("repo.tar", "repo"),
        ("repo.git", "repo"),
        ("REPO.TAR.GZ", "REPO"),  # suffix match is case-insensitive
        ("repo", "repo"),  # no suffix, stem fallback
        ("dir.name/repo.tar.gz", "dir.name/repo"),
    ],
)
def test_strip_archive_suffix(name, expected):
    assert strip_archive_suffix(name) == expected


def test_snapshot_archive_name_basic():
    assert snapshot_archive_name("myrepo.git") == "myrepo-snapshot.tar.gz"


def test_snapshot_archive_name_falls_back_when_seed_empty():
    assert snapshot_archive_name(None) == "source-snapshot.tar.gz"
    assert snapshot_archive_name("") == "source-snapshot.tar.gz"


def test_snapshot_archive_name_respects_custom_fallback():
    assert snapshot_archive_name(None, fallback="origin") == "origin-snapshot.tar.gz"


def test_snapshot_archive_name_strips_archive_suffix_after_safe_filename():
    # path-like seed -> safe_filename keeps last component -> strip -> snapshot
    assert (
        snapshot_archive_name("https://example.com/owner/repo.tar.gz")
        == "repo-snapshot.tar.gz"
    )
