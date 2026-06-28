"""Unit tests for experiment-run evaluation logic."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

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
    ExpectedOutput,
    Experiment,
    FileSource,
    NumericMatch,
    RegexMatch,
    Sha256Match,
    StderrSource,
    StdoutSource,
)
from repo2ree_core.experiment.run import build_capture_bundle


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ================================================
# evaluate_match — sha256
# ================================================


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


def test_build_capture_bundle_collects_stdout_stderr(tmp_path):
    bundle = build_capture_bundle("out", "err", workspace=tmp_path, outputs=[])
    assert bundle.stdout == "out"
    assert bundle.stderr == "err"
    assert bundle.files == {}


def test_build_capture_bundle_reads_file_outputs(tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "out.txt").write_text("data")
    outputs = [
        ExpectedOutput(
            source=FileSource(kind="file", path="results/out.txt"),
            match=ContainsMatch(mode="contains", value="data"),
        )
    ]
    bundle = build_capture_bundle("", "", workspace=tmp_path, outputs=outputs)
    assert bundle.files == {"results/out.txt": b"data"}


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
