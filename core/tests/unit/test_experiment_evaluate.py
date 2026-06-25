"""Unit tests for experiment-run evaluation logic."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic import ValidationError

from repo2ree_core.domain.env_entry import ContainerEntry
from repo2ree_core.experiment.evaluate import (
    CaptureBundle,
    evaluate_match,
    evaluate_output,
    make_run_result,
    snapshot_match_for,
    snapshot_outputs,
)
from repo2ree_core.experiment.experiment import (
    ContainsMatch,
    CustomMatch,
    ExpectedOutput,
    Experiment,
    FileSource,
    NumericMatch,
    RegexMatch,
    Sha256Match,
    StderrSource,
    StdoutSource,
)
from repo2ree_core.experiment.run import (
    _evaluate_custom_match,
    _evaluate_file_output_in_container,
    _snapshot_file_outputs_in_container,
    build_capture_bundle,
    run_runnable,
)
from repo2ree_core.working_environment import (
    ProvisioningCanceledError,
    ScriptStep,
    StepOutcome,
)

# ================================================
# evaluate_match — sha256
# ================================================


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_sha256_match_passes_on_correct_hash():
    content = b"hello world\n"
    match = Sha256Match(mode="sha256", value=_sha256(content))
    passed, detail = evaluate_match(match, content.decode(), content)
    assert passed
    assert "matched" in detail


def test_sha256_match_fails_on_wrong_hash():
    match = Sha256Match(mode="sha256", value="a" * 64)
    passed, _ = evaluate_match(match, "hello", b"hello")
    assert not passed


def test_sha256_uses_raw_bytes_when_provided():
    raw = b"\xff\xfe"
    text = raw.decode("utf-8", errors="replace")
    match = Sha256Match(mode="sha256", value=_sha256(raw))
    passed, _ = evaluate_match(match, text, raw)
    assert passed


def test_sha256_falls_back_to_utf8_when_no_raw():
    text = "hello"
    match = Sha256Match(mode="sha256", value=_sha256(text.encode("utf-8")))
    passed, _ = evaluate_match(match, text, None)
    assert passed


# ================================================
# evaluate_match — contains
# ================================================


def test_contains_match_passes():
    match = ContainsMatch(mode="contains", value="PASSED")
    passed, _ = evaluate_match(match, "Test suite: PASSED (12 tests)", None)
    assert passed


def test_contains_match_fails():
    match = ContainsMatch(mode="contains", value="PASSED")
    passed, detail = evaluate_match(match, "FAILED", None)
    assert not passed
    assert "not found" in detail


# ================================================
# evaluate_match — regex
# ================================================


def test_regex_match_passes():
    match = RegexMatch(mode="regex", value=r"accuracy: 0\.\d+")
    passed, _ = evaluate_match(match, "accuracy: 0.9542", None)
    assert passed


def test_regex_match_fails():
    match = RegexMatch(mode="regex", value=r"accuracy: 0\.\d+")
    passed, _ = evaluate_match(match, "no accuracy here", None)
    assert not passed


def test_regex_match_invalid_pattern_fails_gracefully():
    match = RegexMatch(mode="regex", value="[invalid(")
    passed, detail = evaluate_match(match, "anything", None)
    assert not passed
    assert "invalid regex" in detail


# ================================================
# evaluate_match — numeric
# ================================================


def test_numeric_match_within_epsilon():
    match = NumericMatch(mode="numeric", value="0.9542", epsilon=0.01)
    passed, _ = evaluate_match(match, "0.9550\n", None)
    assert passed


def test_numeric_match_outside_epsilon():
    match = NumericMatch(mode="numeric", value="0.9542", epsilon=0.001)
    passed, _ = evaluate_match(match, "0.9600", None)
    assert not passed


def test_numeric_match_fails_on_non_number():
    match = NumericMatch(mode="numeric", value="1.0", epsilon=0.01)
    passed, detail = evaluate_match(match, "not a number", None)
    assert not passed
    assert "not a number" in detail


# ================================================
# evaluate_output
# ================================================


def test_evaluate_stdout_output():
    captures = CaptureBundle(stdout="Test PASSED\n")
    exp = ExpectedOutput(
        source=StdoutSource(kind="stdout"),
        match=ContainsMatch(mode="contains", value="PASSED"),
    )
    result = evaluate_output(exp, captures)
    assert result.passed
    assert result.source_key == "stdout"


def test_evaluate_stderr_output():
    captures = CaptureBundle(stderr="WARNING: something\n")
    exp = ExpectedOutput(
        source=StderrSource(kind="stderr"),
        match=ContainsMatch(mode="contains", value="WARNING"),
    )
    result = evaluate_output(exp, captures)
    assert result.passed


def test_evaluate_file_output_pass():
    raw = b"result: 42\n"
    captures = CaptureBundle(files={"output.txt": raw})
    exp = ExpectedOutput(
        source=FileSource(kind="file", path="output.txt"),
        match=Sha256Match(mode="sha256", value=_sha256(raw)),
    )
    result = evaluate_output(exp, captures)
    assert result.passed
    assert result.source_key == "file:output.txt"


def test_evaluate_file_output_missing():
    captures = CaptureBundle()
    exp = ExpectedOutput(
        source=FileSource(kind="file", path="missing.txt"),
        match=Sha256Match(mode="sha256", value="a" * 64),
    )
    result = evaluate_output(exp, captures)
    assert not result.passed
    assert "not found" in result.detail


# ================================================
# make_run_result
# ================================================


def test_run_passes_with_no_outputs_and_exit_zero():
    result = make_run_result(0, [])
    assert result.verdict == "pass"
    assert result.output_results == []


def test_run_fails_on_nonzero_exit():
    result = make_run_result(1, [])
    assert result.verdict == "fail"


def test_run_fails_when_output_mismatches():
    exp = ExpectedOutput(
        source=StdoutSource(kind="stdout"),
        match=ContainsMatch(mode="contains", value="PASSED"),
    )
    captures = CaptureBundle(stdout="FAILED\n")
    output_results = [evaluate_output(exp, captures)]
    result = make_run_result(0, output_results)
    assert result.verdict == "fail"
    assert not result.output_results[0].passed


def test_run_passes_with_all_matching_outputs():
    exp = ExpectedOutput(
        source=StdoutSource(kind="stdout"),
        match=ContainsMatch(mode="contains", value="ok"),
    )
    captures = CaptureBundle(stdout="all ok\n")
    output_results = [evaluate_output(exp, captures)]
    result = make_run_result(0, output_results)
    assert result.verdict == "pass"


# ================================================
# snapshot
# ================================================


def test_snapshot_match_for_stdout():
    text = "accuracy: 0.9542\n"
    match = snapshot_match_for(text, None)
    assert match.mode == "sha256"
    expected_hash = _sha256(text.encode("utf-8"))
    assert match.value == expected_hash


def test_snapshot_match_for_file_uses_raw_bytes():
    raw = b"\x00\x01\x02"
    text = raw.decode("utf-8", errors="replace")
    match = snapshot_match_for(text, raw)
    assert match.value == _sha256(raw)


def test_snapshot_outputs_replaces_sha256_with_current_hash():
    text = "accuracy: 0.9542\n"
    outputs = [
        ExpectedOutput(
            source=StdoutSource(kind="stdout"),
            match=Sha256Match(mode="sha256", value="a" * 64),
        )
    ]
    captures = CaptureBundle(stdout=text)
    result = snapshot_outputs(outputs, captures)
    assert len(result) == 1
    assert result[0].match.mode == "sha256"
    assert result[0].match.value == _sha256(text.encode())


def test_snapshot_outputs_preserves_non_sha256_matcher():
    outputs = [
        ExpectedOutput(
            source=StdoutSource(kind="stdout"),
            match=ContainsMatch(mode="contains", value="ok"),
        )
    ]
    captures = CaptureBundle(stdout="ok output")
    result = snapshot_outputs(outputs, captures)
    assert len(result) == 1
    assert result[0].match.mode == "contains"
    assert result[0].match.value == "ok"  # type: ignore[union-attr]


def test_snapshot_outputs_preserves_numeric_matcher():
    outputs = [
        ExpectedOutput(
            source=StdoutSource(kind="stdout"),
            match=NumericMatch(mode="numeric", value="0.95", epsilon=0.01),
        )
    ]
    captures = CaptureBundle(stdout="0.9542")
    result = snapshot_outputs(outputs, captures)
    assert len(result) == 1
    assert result[0].match.mode == "numeric"


def test_snapshot_outputs_drops_missing_sha256_stdout():
    outputs = [
        ExpectedOutput(
            source=StdoutSource(kind="stdout"),
            match=Sha256Match(mode="sha256", value="a" * 64),
        ),
    ]
    captures = CaptureBundle(stdout="ok")
    result = snapshot_outputs(outputs, captures)
    assert len(result) == 1
    assert result[0].source.kind == "stdout"


def test_snapshot_outputs_all_stream_sha256_sources():
    outputs = [
        ExpectedOutput(
            source=StdoutSource(kind="stdout"),
            match=Sha256Match(mode="sha256", value="a" * 64),
        ),
        ExpectedOutput(
            source=StderrSource(kind="stderr"),
            match=Sha256Match(mode="sha256", value="a" * 64),
        ),
    ]
    captures = CaptureBundle(stdout="out", stderr="err")
    result = snapshot_outputs(outputs, captures)
    assert len(result) == 2
    assert all(o.match.mode == "sha256" for o in result)


# ================================================
# build_capture_bundle
# ================================================


def test_build_capture_bundle_collects_stdout_stderr():
    bundle = build_capture_bundle("out", "err")
    assert bundle.stdout == "out"
    assert bundle.stderr == "err"
    assert bundle.files == {}


# ================================================
# _evaluate_custom_match
# ================================================


class _FakeWE:
    """Minimal WorkingEnvironment fake for unit tests."""

    def __init__(self, exec_outcome: StepOutcome) -> None:
        self._outcome = exec_outcome
        self.put_calls: list[tuple[str, str]] = []
        self.exec_calls: list[ScriptStep] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def exec_script(self, step: ScriptStep, *, log, is_canceled) -> StepOutcome:
        self.exec_calls.append(step)
        return self._outcome

    def put_file(self, rel_path: str, content: str) -> None:
        self.put_calls.append((rel_path, content))

    def sync_out(self, *, log) -> bool:
        return True


def test_custom_match_runs_validator_inside_runtime(tmp_path):
    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0))

    match = CustomMatch(mode="custom", value="grep -q NEEDLE")
    passed, detail = _evaluate_custom_match(
        match=match,
        text="line1\nNEEDLE\n",
        we=fake_we,
        run_id="run-123",
        output_index=0,
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert passed
    assert detail == "custom script exited 0"
    assert len(fake_we.put_calls) == 1
    assert fake_we.put_calls[0][1] == "grep -q NEEDLE"
    assert len(fake_we.exec_calls) == 1
    step = fake_we.exec_calls[0]
    assert step.stdin_text == "line1\nNEEDLE\n"
    assert step.working_dir_rel == ""


def test_custom_match_fails_on_nonzero_runtime_exit(tmp_path):
    fake_we = _FakeWE(StepOutcome("failed", exit_code=7))

    match = CustomMatch(mode="custom", value="grep -q NEEDLE")
    passed, detail = _evaluate_custom_match(
        match=match,
        text="no match",
        we=fake_we,
        run_id="run-123",
        output_index=0,
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert not passed
    assert detail == "custom script exited 7"


# ================================================
# _evaluate_file_output_in_container
# ================================================


def test_evaluate_file_in_container_sha256_match():
    expected_hash = "a" * 64
    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout=f"{expected_hash}  output.bin\n"))

    exp = ExpectedOutput(
        source=FileSource(kind="file", path="output.bin"),
        match=Sha256Match(mode="sha256", value=expected_hash),
    )
    result = _evaluate_file_output_in_container(
        exp, we=fake_we, run_id="run-1", output_index=0, log=lambda *_: None, is_canceled=lambda: False
    )

    assert result.passed
    assert result.source_key == "file:output.bin"
    assert len(fake_we.put_calls) == 1
    assert "sha256sum" in fake_we.put_calls[0][1]


def test_evaluate_file_in_container_sha256_mismatch():
    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout=f"{'b' * 64}  output.bin\n"))

    exp = ExpectedOutput(
        source=FileSource(kind="file", path="output.bin"),
        match=Sha256Match(mode="sha256", value="a" * 64),
    )
    result = _evaluate_file_output_in_container(
        exp, we=fake_we, run_id="run-1", output_index=0, log=lambda *_: None, is_canceled=lambda: False
    )

    assert not result.passed
    assert "mismatch" in result.detail


def test_evaluate_file_in_container_file_not_found():
    fake_we = _FakeWE(StepOutcome("failed", exit_code=1))

    exp = ExpectedOutput(
        source=FileSource(kind="file", path="/results/missing.png"),
        match=Sha256Match(mode="sha256", value="a" * 64),
    )
    result = _evaluate_file_output_in_container(
        exp, we=fake_we, run_id="run-1", output_index=0, log=lambda *_: None, is_canceled=lambda: False
    )

    assert not result.passed
    assert "not found" in result.detail


def test_evaluate_file_in_container_contains_match():
    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout="accuracy: 0.95\n"))

    exp = ExpectedOutput(
        source=FileSource(kind="file", path="/results/summary.txt"),
        match=ContainsMatch(mode="contains", value="accuracy"),
    )
    result = _evaluate_file_output_in_container(
        exp, we=fake_we, run_id="run-1", output_index=0, log=lambda *_: None, is_canceled=lambda: False
    )

    assert result.passed
    assert len(fake_we.put_calls) == 1
    assert "cat" in fake_we.put_calls[0][1]


def test_evaluate_file_in_container_absolute_path_passed_to_script():
    digest = "a" * 64
    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout=f"{digest}  /results/foo.png\n"))

    exp = ExpectedOutput(
        source=FileSource(kind="file", path="/results/foo.png"),
        match=Sha256Match(mode="sha256", value=digest),
    )
    _evaluate_file_output_in_container(
        exp, we=fake_we, run_id="run-1", output_index=0, log=lambda *_: None, is_canceled=lambda: False
    )

    # The script content must reference the absolute path so the runtime can find it.
    assert "/results/foo.png" in fake_we.put_calls[0][1]


# ================================================
# _snapshot_file_outputs_in_container
# ================================================


def test_snapshot_file_in_container_records_hash():
    digest = "a" * 64
    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout=f"{digest}  output.bin\n"))

    file_outputs = [
        ExpectedOutput(
            source=FileSource(kind="file", path="output.bin"),
            match=Sha256Match(mode="sha256", value="old" * 20 + "xxxx"),
        )
    ]
    result = _snapshot_file_outputs_in_container(
        file_outputs, we=fake_we, run_id="run-1", log=lambda *_: None, is_canceled=lambda: False
    )

    assert len(result) == 1
    assert result[0].match.value == digest


def test_snapshot_file_in_container_preserves_non_sha256():
    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0))

    file_outputs = [
        ExpectedOutput(
            source=FileSource(kind="file", path="out.txt"),
            match=ContainsMatch(mode="contains", value="ok"),
        )
    ]
    result = _snapshot_file_outputs_in_container(
        file_outputs, we=fake_we, run_id="run-1", log=lambda *_: None, is_canceled=lambda: False
    )

    assert len(result) == 1
    assert result[0].match.mode == "contains"
    assert len(fake_we.put_calls) == 0


def test_snapshot_file_in_container_drops_missing():
    fake_we = _FakeWE(StepOutcome("failed", exit_code=1))

    file_outputs = [
        ExpectedOutput(
            source=FileSource(kind="file", path="/results/missing.png"),
            match=Sha256Match(mode="sha256", value="a" * 64),
        )
    ]
    result = _snapshot_file_outputs_in_container(
        file_outputs, we=fake_we, run_id="run-1", log=lambda *_: None, is_canceled=lambda: False
    )

    assert result == []


# ================================================
# experiment name validation
# ================================================


@pytest.mark.parametrize("name", ["smoke", "smoke-test", "smoke_test", "smoke.v2", "My Test 1", ""])
def test_experiment_name_accepts_path_safe_names(name):
    assert Experiment(name=name).name == name


@pytest.mark.parametrize("name", ["a/b", "../escape", ".", "..", "exp?run", "exp#1"])
def test_experiment_name_rejects_path_unsafe_names(name):
    with pytest.raises(ValidationError):
        Experiment(name=name)


# ================================================
# run_experiment semantics
# ================================================


def test_run_experiment_marks_verify_mismatch_as_failed(tmp_path, monkeypatch):
    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout="FAILED\n"))

    @contextmanager
    def fake_loaded_runtime_image(*args, **kwargs):
        yield "runtime:test"

    @contextmanager
    def fake_acquire(workspace, run_id, *, log, image=None, **kwargs):
        assert image == "runtime:test"
        yield fake_we

    monkeypatch.setattr("repo2ree_core.experiment.run.acquire", fake_acquire)
    monkeypatch.setattr(
        "repo2ree_core.experiment.run.loaded_runtime_image",
        fake_loaded_runtime_image,
    )

    experiment = Experiment(
        name="smoke",
        command="echo FAILED",
        outputs=[
            ExpectedOutput(
                source=StdoutSource(kind="stdout"),
                match=ContainsMatch(mode="contains", value="PASSED"),
            )
        ],
    )

    result = run_runnable(
        workspace=tmp_path,
        runnable=experiment,
        label=experiment.name,
        mode="verify",
        entry=ContainerEntry(),
        runtime_archive_path=tmp_path / "runtime.tar.gz",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "failed"
    assert result.run_outputs["verdict"] == "fail"
    assert len(fake_we.exec_calls) == 1
    assert fake_we.exec_calls[0].working_dir_rel == ""


def test_run_experiment_canceled_skips_output_evaluation(tmp_path, monkeypatch):
    evaluated = []
    fake_we = _FakeWE(StepOutcome("canceled", exit_code=None))

    @contextmanager
    def fake_loaded_runtime_image(*args, **kwargs):
        yield "runtime:test"

    @contextmanager
    def fake_acquire(workspace, run_id, *, log, image=None, **kwargs):
        yield fake_we

    monkeypatch.setattr("repo2ree_core.experiment.run.acquire", fake_acquire)
    monkeypatch.setattr(
        "repo2ree_core.experiment.run.loaded_runtime_image",
        fake_loaded_runtime_image,
    )
    monkeypatch.setattr(
        "repo2ree_core.experiment.run.evaluate_output",
        lambda *a, **kw: evaluated.append(a) or None,
    )

    experiment = Experiment(
        name="smoke",
        command="echo ok",
        outputs=[
            ExpectedOutput(
                source=StdoutSource(kind="stdout"),
                match=ContainsMatch(mode="contains", value="ok"),
            )
        ],
    )

    result = run_runnable(
        workspace=tmp_path,
        runnable=experiment,
        label=experiment.name,
        mode="verify",
        entry=ContainerEntry(),
        runtime_archive_path=tmp_path / "runtime.tar.gz",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "canceled"
    assert evaluated == []


def test_run_experiment_returns_canceled_when_provisioning_is_canceled(tmp_path, monkeypatch):
    @contextmanager
    def fake_loaded_runtime_image(*args, **kwargs):
        yield "runtime:test"

    @contextmanager
    def fake_acquire(workspace, run_id, *, log, image=None, **kwargs):
        raise ProvisioningCanceledError("Run canceled during provisioning")
        yield

    monkeypatch.setattr("repo2ree_core.experiment.run.acquire", fake_acquire)
    monkeypatch.setattr(
        "repo2ree_core.experiment.run.loaded_runtime_image",
        fake_loaded_runtime_image,
    )

    experiment = Experiment(
        name="smoke",
        command="echo ok",
        outputs=[],
    )

    result = run_runnable(
        workspace=tmp_path,
        runnable=experiment,
        label=experiment.name,
        mode="verify",
        entry=ContainerEntry(),
        runtime_archive_path=tmp_path / "runtime.tar.gz",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: True,
    )

    assert result.status == "canceled"
    # Canceled during provisioning: the image tag only lives inside the
    # environment context manager, so the record reports no runtime image.
    assert result.run_outputs["substrate"] is None
    assert result.run_outputs["exitCode"] is None


def _patch_env(monkeypatch, fake_we):
    @contextmanager
    def fake_loaded_runtime_image(*args, **kwargs):
        yield "runtime:test"

    @contextmanager
    def fake_acquire(workspace, run_id, *, log, image=None, **kwargs):
        yield fake_we

    monkeypatch.setattr("repo2ree_core.experiment.run.acquire", fake_acquire)
    monkeypatch.setattr("repo2ree_core.experiment.run.loaded_runtime_image", fake_loaded_runtime_image)


def test_exec_override_dispatches_command_with_abi_env(tmp_path, monkeypatch):
    from repo2ree_core.domain.env_entry import ContainerEntry, PhaseOverrides

    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout="ok\n"))
    _patch_env(monkeypatch, fake_we)

    experiment = Experiment(name="smoke", command="echo ok", outputs=[])
    result = run_runnable(
        workspace=tmp_path,
        runnable=experiment,
        label=experiment.name,
        mode="verify",
        entry=ContainerEntry(overrides=PhaseOverrides(exec="code/run")),
        runtime_archive_path=tmp_path / "runtime.tar.gz",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    # The command step targets the override script, handed the dispatch ABI.
    assert len(fake_we.exec_calls) == 1
    step = fake_we.exec_calls[0]
    assert step.script_rel_path == "code/run"
    assert step.env == {"R2R_COMMAND": ".workspace/exp_run-123.sh", "R2R_RUN_ID": "run-123"}


def test_no_override_runs_command_script_directly(tmp_path, monkeypatch):
    from repo2ree_core.domain.env_entry import ContainerEntry

    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout="ok\n"))
    _patch_env(monkeypatch, fake_we)

    experiment = Experiment(name="smoke", command="echo ok", outputs=[])
    run_runnable(
        workspace=tmp_path,
        runnable=experiment,
        label=experiment.name,
        mode="verify",
        entry=ContainerEntry(),
        runtime_archive_path=tmp_path / "runtime.tar.gz",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    step = fake_we.exec_calls[0]
    assert step.script_rel_path == ".workspace/exp_run-123.sh"
    assert step.env == {}


def test_provision_hook_runs_before_command(tmp_path, monkeypatch):
    from repo2ree_core.domain.env_entry import ContainerEntry, PhaseOverrides

    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout="ok\n"))
    _patch_env(monkeypatch, fake_we)

    experiment = Experiment(name="smoke", command="echo ok", outputs=[])
    run_runnable(
        workspace=tmp_path,
        runnable=experiment,
        label=experiment.name,
        mode="verify",
        entry=ContainerEntry(overrides=PhaseOverrides(provision="scripts/up")),
        runtime_archive_path=tmp_path / "runtime.tar.gz",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert [s.script_rel_path for s in fake_we.exec_calls] == ["scripts/up", ".workspace/exp_run-123.sh"]


def test_failed_provision_hook_aborts_run_before_command(tmp_path, monkeypatch):
    from repo2ree_core.domain.env_entry import ContainerEntry, PhaseOverrides

    fake_we = _FakeWE(StepOutcome("failed", exit_code=3))
    _patch_env(monkeypatch, fake_we)

    experiment = Experiment(name="smoke", command="echo ok", outputs=[])
    result = run_runnable(
        workspace=tmp_path,
        runnable=experiment,
        label=experiment.name,
        mode="verify",
        entry=ContainerEntry(overrides=PhaseOverrides(provision="scripts/up")),
        runtime_archive_path=tmp_path / "runtime.tar.gz",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "failed"
    # Only the provision hook ran; the command was never dispatched.
    assert [s.script_rel_path for s in fake_we.exec_calls] == ["scripts/up"]


def test_teardown_hook_runs_after_command(tmp_path, monkeypatch):
    from repo2ree_core.domain.env_entry import ContainerEntry, PhaseOverrides

    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout="ok\n"))
    _patch_env(monkeypatch, fake_we)

    experiment = Experiment(name="smoke", command="echo ok", outputs=[])
    run_runnable(
        workspace=tmp_path,
        runnable=experiment,
        label=experiment.name,
        mode="verify",
        entry=ContainerEntry(overrides=PhaseOverrides(teardown="scripts/down")),
        runtime_archive_path=tmp_path / "runtime.tar.gz",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    # Teardown runs in the finally, after the command step.
    assert [s.script_rel_path for s in fake_we.exec_calls] == [".workspace/exp_run-123.sh", "scripts/down"]


def test_run_experiment_ignores_cleanup_unlink_errors(tmp_path, monkeypatch):
    fake_we = _FakeWE(StepOutcome("succeeded", exit_code=0, captured_stdout="ok\n"))
    original_unlink = Path.unlink

    @contextmanager
    def fake_loaded_runtime_image(*args, **kwargs):
        yield "runtime:test"

    @contextmanager
    def fake_acquire(workspace, run_id, *, log, image=None, **kwargs):
        yield fake_we

    def flaky_unlink(path: Path, *args, **kwargs):
        if path.name == "exp_run-123.sh":
            raise OSError("cleanup failed")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr("repo2ree_core.experiment.run.acquire", fake_acquire)
    monkeypatch.setattr(
        "repo2ree_core.experiment.run.loaded_runtime_image",
        fake_loaded_runtime_image,
    )
    monkeypatch.setattr("pathlib.Path.unlink", flaky_unlink)

    experiment = Experiment(
        name="smoke",
        command="echo ok",
        outputs=[
            ExpectedOutput(
                source=StdoutSource(kind="stdout"),
                match=ContainsMatch(mode="contains", value="ok"),
            )
        ],
    )

    result = run_runnable(
        workspace=tmp_path,
        runnable=experiment,
        label=experiment.name,
        mode="verify",
        entry=ContainerEntry(),
        runtime_archive_path=tmp_path / "runtime.tar.gz",
        run_id="run-123",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    assert result.run_outputs["verdict"] == "pass"
