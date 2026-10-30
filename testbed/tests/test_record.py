from pathlib import Path

from repo2ree_testbed.runs.record import outcomes

REPORT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest">
    <testcase classname="tests.test_a" name="test_passes"/>
    <testcase classname="tests.test_a" name="test_fails"><failure message="assert 1 == 2"/></testcase>
    <testcase classname="tests.test_a" name="test_errors"><error message="fixture broke"/></testcase>
    <testcase classname="tests.test_a" name="test_needs_docker"><skipped message="no docker"/></testcase>
  </testsuite>
</testsuites>
"""


def test_every_case_of_every_report_is_a_test_with_its_outcome(tmp_path: Path) -> None:
    (tmp_path / "core.xml").write_text(REPORT)
    (tmp_path / "playwright.xml").write_text(
        '<testsuites><testsuite><testcase name="renders"/></testsuite></testsuites>'
    )

    tests = outcomes(tmp_path, 1.0, 2.0)

    assert [(test.name, test.outcome, test.reason) for test in tests] == [
        ("tests.test_a::test_passes", "passed", ""),
        ("tests.test_a::test_fails", "failed", "assert 1 == 2"),
        ("tests.test_a::test_errors", "failed", "fixture broke"),
        ("tests.test_a::test_needs_docker", "skipped", "no docker"),
        ("renders", "passed", ""),
    ]
