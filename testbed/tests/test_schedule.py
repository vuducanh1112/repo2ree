import pytest

from repo2ree_testbed.records import RunRecord
from repo2ree_testbed.runs.e2e import parse
from repo2ree_testbed.runs.schedule import PerTest, selected
from repo2ree_testbed.stack.clients import TestCase

CASES = [
    TestCase(name, name.replace("::", "--"), (name,))
    for name in (
        "api/tests/system/test_authoring.py::test_sealed_ree_is_frozen",
        "api/tests/system/test_authoring.py::test_a_bundle_never_loads_into_a_sealed_ree",
        "api/tests/system/test_failures.py::test_canceling_a_running_build",
    )
]


def test_a_selection_keeps_the_tests_whose_id_contains_any_of_its_parts() -> None:
    assert selected(CASES, ("test_authoring.py",), "e2e-system") == CASES[:2]
    assert selected(CASES, ("sealed_ree_is_frozen", "canceling"), "e2e-system") == [CASES[0], CASES[2]]
    assert selected(CASES, (CASES[1].name,), "e2e-system") == [CASES[1]]


def test_a_selection_that_matches_nothing_is_refused() -> None:
    with pytest.raises(RuntimeError, match="no test of the e2e-system suite matches test_nothing"):
        selected(CASES, ("test_nothing",), "e2e-system")


def test_a_selection_is_parts_of_test_ids_given_on_the_command_line() -> None:
    command = ["--script", "suite.py", "--tier", "e2e-system", "--per-test"]
    assert parse(command).schedule == PerTest(1, ())
    assert parse([*command, "--select", "test_a test_b"]).schedule == PerTest(1, ("test_a", "test_b"))
    assert parse([*command, "--select", "test_a", "--select", "test_c"]).schedule == PerTest(1, ("test_a", "test_c"))
    # A recipe passes no selection as an empty one.
    assert parse([*command, "--select", ""]).schedule == PerTest(1, ())


def test_a_run_records_what_it_was_limited_to() -> None:
    whole = RunRecord(tier="e2e-system", suite="s", build_revision="r", jobs=1, tests=())
    assert whole.selected == ()
    assert RunRecord.model_validate_json(whole.but(selected=("test_a",)).model_dump_json()).selected == ("test_a",)
