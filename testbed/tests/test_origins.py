import subprocess
import tarfile
from pathlib import Path

from repo2ree_testbed.stack import origins


def head(repository: Path) -> str:
    return subprocess.run(
        ["git", "--git-dir", str(repository), "rev-parse", "main"], check=True, capture_output=True, text=True
    ).stdout.strip()


def test_every_build_of_the_fixture_is_the_same_commit_and_the_same_tarball(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()

    assert head(origins.build_repository(first)) == head(origins.build_repository(second))
    assert origins.build_tarball(first).read_bytes() == origins.build_tarball(second).read_bytes()
    with tarfile.open(first / origins.TARBALL) as archive:
        assert "ree-e2e-fixture/hello.py" in archive.getnames()


def test_a_stack_serves_the_fixture_by_git_and_over_http(tmp_path: Path) -> None:
    served_origins = origins.Origins(tmp_path / "served", "127.0.0.1")
    try:
        served = served_origins.start(tmp_path / "origins.log")
        clone = tmp_path / "clone"
        subprocess.run(["git", "clone", "-q", "--depth", "1", served.git_url, str(clone)], check=True)
        assert (clone / "hello.py").is_file()
        # A review fetches the recorded commit by its id, shallow, as the product's acquire script does.
        commit = head(tmp_path / "served" / origins.REPOSITORY)
        pinned = tmp_path / "pinned"
        subprocess.run(["git", "init", "-q", str(pinned)], check=True)
        subprocess.run(["git", "-C", str(pinned), "fetch", "-q", "--depth", "1", served.git_url, commit], check=True)
        fetched = subprocess.run(["curl", "-fsS", served.tarball_url], check=True, capture_output=True).stdout
        assert fetched == (tmp_path / "served" / origins.TARBALL).read_bytes()
    finally:
        served_origins.stop()
    assert served.environment() == {
        "E2E_GIT_ORIGIN_URL": served.git_url,
        "E2E_TARBALL_ORIGIN_URL": served.tarball_url,
    }
