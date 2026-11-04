from pathlib import Path

import pytest

from repo2ree_testbed.records import RunRecord, RunTest
from repo2ree_testbed.runs import assess, visualize


def run_test(directory: str, rees: tuple[str, ...] = ()) -> RunTest:
    return RunTest(
        name=directory,
        selection=(),
        outcome="passed",
        reason="",
        exit_code=0,
        started=0,
        finished=1,
        rees=rees,
        phases={},
        directory=directory,
    )


@pytest.fixture
def traceview(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """Traceview as asked to run, drawing one page wherever it is pointed."""
    ran: list[tuple[str, ...]] = []

    def tool(log: Path, *args: str) -> int:
        ran.append(args)
        traces = Path(args[args.index("-o") + 1])
        traces.mkdir(parents=True, exist_ok=True)
        (traces / "ree-1.html").write_text("<html></html>")
        return 0

    monkeypatch.setattr(visualize, "tool", tool)
    return ran


def judged(directory: Path) -> None:
    (directory / "verification").mkdir(parents=True)
    (directory / "verification/verification.json").write_text("{}")


def test_a_run_has_the_traces_of_its_judged_tests_with_rees_drawn_and_linked(
    tmp_path: Path, traceview: list[tuple[str, ...]]
) -> None:
    run = tmp_path / "e2e-system-1"
    tests = (run_test("tests/drawn", rees=("ree-1",)), run_test("tests/no-ree"), run_test("tests/unjudged", ("r",)))
    for test in tests:
        (run / test.directory).mkdir(parents=True)
    judged(run / "tests/drawn")
    judged(run / "tests/no-ree")
    (run / "run.json").write_text(
        RunRecord(tier="t", suite="s", build_revision="", jobs=1, tests=tests).model_dump_json()
    )

    visualize.visualize_run(run)

    [trace] = traceview
    assert trace[1:3] == ("trace", str(run / "tests/drawn/verification"))
    assert trace[trace.index("-o") + 1] == str(run / "tests/drawn/traces")
    assert "traces/ree-1.html" in (run / "tests/drawn/index.html").read_text()
    assert (run / "index.html").is_file()


def test_a_collected_dossier_is_drawn_beside_its_verification_only_once_judged(
    tmp_path: Path, traceview: list[tuple[str, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REPO2REE_ASSURANCE_DIR", str(tmp_path / "assurance"))
    dossier = tmp_path / "collected"
    dossier.mkdir()
    with pytest.raises(ValueError, match="no verification to draw from; assess it first"):
        visualize.visualize_dossier(dossier)

    (tmp_path / "assurance/verification/collected").mkdir(parents=True)
    (tmp_path / "assurance/verification/collected/verification.json").write_text("{}")
    visualize.visualize_dossier(dossier)
    [trace] = traceview
    assert trace[trace.index("-o") + 1] == str(tmp_path / "assurance/traces/collected")


def test_assessing_only_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[tuple[str, ...]] = []

    def tool(log: Path, *args: str) -> int:
        ran.append(args)
        return 0

    monkeypatch.setattr(assess, "tool", tool)
    directory = tmp_path / "run/tests/t"
    (directory / "dossier").mkdir(parents=True)
    (directory / "dossier/manifest.json").write_text("{}")
    assess.assess_test(directory, run_test("tests/t", rees=("r",)))
    assert [args[0] for args in ran] == ["repo2ree_assurance_checker"]
    assert not (directory / "index.html").exists()
