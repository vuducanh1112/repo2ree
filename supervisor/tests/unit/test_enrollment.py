from pathlib import Path

import pytest

from repo2ree_protocol.workbench import WorkbenchHello
from repo2ree_supervisor.enrollment import EnrollmentRegistry


def _hello(presented: str = "token-a", workbench_id: str = "wb-a") -> WorkbenchHello:
    return WorkbenchHello(workbench_id=workbench_id, allocation_id="alloc-a", enrollment_token=presented)


def test_a_bench_enrolled_before_a_restart_is_known_after_it(tmp_path: Path) -> None:
    path = tmp_path / "enrollments.json"
    EnrollmentRegistry(path).expect("alloc-a", "wb-a", "token-a")

    restarted = EnrollmentRegistry(path)

    restarted.authenticate(_hello())
    with pytest.raises(ValueError, match="does not match"):
        restarted.authenticate(_hello(presented="token-b"))
    with pytest.raises(ValueError, match="does not match"):
        restarted.authenticate(_hello(workbench_id="wb-b"))


def test_a_released_allocation_is_forgotten_across_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "enrollments.json"
    registry = EnrollmentRegistry(path)
    registry.expect("alloc-a", "wb-a", "token-a")
    registry.discard("alloc-a")

    with pytest.raises(ValueError, match="unknown workbench enrollment"):
        EnrollmentRegistry(path).authenticate(_hello())


def test_only_digests_are_stored_and_only_their_owner_reads_them(tmp_path: Path) -> None:
    path = tmp_path / "enrollments.json"
    EnrollmentRegistry(path).expect("alloc-a", "wb-a", "token-a")

    assert "token-a" not in path.read_text()
    assert path.stat().st_mode & 0o077 == 0


def test_without_a_file_nothing_is_written(tmp_path: Path) -> None:
    registry = EnrollmentRegistry()
    registry.expect("alloc-a", "wb-a", "token-a")

    registry.authenticate(_hello())
    assert list(tmp_path.iterdir()) == []
