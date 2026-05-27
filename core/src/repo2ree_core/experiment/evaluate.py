"""Pure experiment-run evaluation logic.

No I/O, no subprocess, no HTTP.  Receives already-captured values and returns
verdicts.  Custom match evaluation (requires subprocess) lives in ``run.py``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal

from repo2ree_core.experiment.experiment import (
    ExpectedOutput,
    OutputMatch,
    OutputSource,
    Sha256Match,
)


# ================================================
# Capture bundle
# ================================================


@dataclass
class CaptureBundle:
    """Outputs captured from a single experiment command execution."""

    stdout: str = ""
    stderr: str = ""
    files: dict[str, bytes] = field(
        default_factory=dict
    )  # workspace-relative path -> bytes

    def text_for(self, source: OutputSource) -> str | None:
        """Return UTF-8 text for *source*, or None if the file is missing."""
        if source.kind == "stdout":
            return self.stdout
        if source.kind == "stderr":
            return self.stderr
        raw = self.files.get(source.path)
        if raw is None:
            return None
        return raw.decode("utf-8", errors="replace")

    def raw_bytes_for(self, source: OutputSource) -> bytes | None:
        """Return raw bytes for *source* (only meaningful for file sources)."""
        if source.kind == "file":
            return self.files.get(source.path)
        return None


# ================================================
# Per-output result
# ================================================


@dataclass
class OutputResult:
    source_key: str  # "stdout", "stderr", or "file:<path>"
    mode: str  # match mode name
    passed: bool
    detail: str


# ================================================
# Experiment run result
# ================================================


@dataclass
class ExperimentRunResult:
    """Aggregated result for a single experiment run (verification)."""

    verdict: Literal["pass", "fail"]
    exit_code: int | None
    output_results: list[OutputResult]


# ================================================
# Pure matching
# ================================================


def source_key(source: OutputSource) -> str:
    if source.kind == "file":
        return f"file:{source.path}"
    return source.kind


def evaluate_match(
    match: OutputMatch, text: str, raw_bytes: bytes | None
) -> tuple[bool, str]:
    """Return (passed, detail) for *match* against the captured value.

    ``text`` is the UTF-8 decoded content; ``raw_bytes`` is only used by the
    sha256 mode for file sources where byte-exact hashing matters.
    """
    if match.mode == "sha256":
        content = raw_bytes if raw_bytes is not None else text.encode("utf-8")
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash == match.value:
            return True, f"sha256 matched ({actual_hash[:12]}…)"
        return (
            False,
            f"sha256 mismatch: got {actual_hash[:12]}…, expected {match.value[:12]}…",
        )

    if match.mode == "contains":
        if match.value in text:
            return True, f"contains {repr(match.value[:40])}"
        return False, f"substring not found: {repr(match.value[:40])}"

    if match.mode == "regex":
        try:
            m = re.search(match.value, text)
        except re.error as exc:
            return False, f"invalid regex: {exc}"
        if m:
            return True, f"regex matched: {repr(m.group(0)[:40])}"
        return False, f"regex not matched: {repr(match.value[:40])}"

    if match.mode == "numeric":
        stripped = text.strip()
        try:
            actual_val = float(stripped)
        except ValueError:
            return False, f"not a number: {repr(stripped[:40])}"
        try:
            expected_val = float(match.value)
        except ValueError:
            return False, f"invalid expected value: {repr(match.value[:40])}"
        diff = abs(actual_val - expected_val)
        if diff <= match.epsilon:
            return (
                True,
                f"|{actual_val} − {expected_val}| = {diff:.3g} ≤ {match.epsilon}",
            )
        return False, f"|{actual_val} − {expected_val}| = {diff:.3g} > {match.epsilon}"

    if match.mode == "custom":
        # Requires imperative shell; the pure layer cannot evaluate this.
        return False, "custom match mode is not evaluated in the pure core"

    return False, f"unknown match mode: {match.mode!r}"


def evaluate_output(expected: ExpectedOutput, captures: CaptureBundle) -> OutputResult:
    """Evaluate a single expected output against *captures*."""
    source = expected.source
    key = source_key(source)
    text = captures.text_for(source)

    if text is None:
        return OutputResult(
            source_key=key,
            mode=expected.match.mode,
            passed=False,
            detail=f"file not found: {source.path!r}",  # type: ignore[union-attr]
        )

    raw = captures.raw_bytes_for(source)
    passed, detail = evaluate_match(expected.match, text, raw)

    return OutputResult(
        source_key=key, mode=expected.match.mode, passed=passed, detail=detail
    )


def make_run_result(
    exit_code: int | None,
    output_results: list[OutputResult],
) -> ExperimentRunResult:
    """Compute the overall verdict from an assembled list of per-output results.

    A run passes iff exit code is 0 and every declared output passes.
    An empty *output_results* list with exit code 0 is also a pass.
    """
    command_ok = exit_code == 0
    outputs_ok = all(r.passed for r in output_results)
    verdict: Literal["pass", "fail"] = "pass" if (command_ok and outputs_ok) else "fail"
    return ExperimentRunResult(
        verdict=verdict,
        exit_code=exit_code,
        output_results=output_results,
    )


# ================================================
# Snapshot
# ================================================


def snapshot_match_for(text: str, raw_bytes: bytes | None) -> OutputMatch:
    """Produce a sha256-based baseline match from a captured value."""
    content = raw_bytes if raw_bytes is not None else text.encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    return Sha256Match(mode="sha256", value=digest)


def snapshot_outputs(
    outputs: list[ExpectedOutput],
    captures: CaptureBundle,
) -> list[ExpectedOutput]:
    """Return a new outputs list with sha256 baselines recorded from *captures*.

    Only sha256-mode outputs are re-hashed — other modes (contains, regex,
    numeric, custom) are preserved unchanged, since the user set them
    intentionally for non-deterministic output.  Sha256 outputs whose source
    file is missing are dropped (cannot snapshot what isn't there).
    """
    result: list[ExpectedOutput] = []
    for expected in outputs:
        if expected.match.mode != "sha256":
            result.append(expected)
            continue
        source = expected.source
        text = captures.text_for(source)
        if text is None:
            continue  # file missing — drop from snapshot
        raw = captures.raw_bytes_for(source)
        match = snapshot_match_for(text, raw)
        result.append(ExpectedOutput(source=source, match=match))
    return result
