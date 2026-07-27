"""Property-based invariants for script inference.

Line coverage over hand-picked examples flatters the parts of this system whose
correctness is a "for *any* input" claim: the REE-name slug must always be a
valid Docker tag, ``resolve_logical_root`` must peel single-child chains without
escaping, the score-free resolver must follow one fixed policy regardless of
order, and a ``complete``/``automatic_allowed`` build must never carry a
blocking warning or an empty body. These are exercised generatively here.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Literal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from scriptinfer_helpers import MemoryAccessor, docker_archive, venv_archive

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.script_inference import ScriptTargetSelector, infer_scripts
from repo2ree_core.script_inference.artifact_inspection import (
    VenvArchiveInspection,
    inspect_runtime_artifact,
)
from repo2ree_core.script_inference.models import StrategyOutcome
from repo2ree_core.script_inference.renderers._common import runtime_image_ref
from repo2ree_core.script_inference.repository_facts import resolve_logical_root
from repo2ree_core.script_inference.resolvers import ScoreFreeViabilityResolver
from repo2ree_core.script_inference.runtime_inputs import RuntimeInputs

pytestmark = pytest.mark.property

_DOCKER_TAG_REF = re.compile(r"ree-runtime:[a-z0-9_][a-z0-9_.-]{0,127}")


# ================================================
# Image-tag slug: any string -> a valid docker reference
# ================================================


@given(st.text(max_size=300))
def test_runtime_image_ref_is_always_a_valid_docker_reference(name: str) -> None:
    ref = runtime_image_ref(name)
    assert _DOCKER_TAG_REF.fullmatch(ref), ref


@given(st.text(alphabet="  \t\n.-_/", max_size=20))
def test_pathological_names_fall_back_but_stay_valid(name: str) -> None:
    # Names that are all separators/whitespace still yield a usable tag.
    ref = runtime_image_ref(name)
    assert _DOCKER_TAG_REF.fullmatch(ref), ref


# ================================================
# Score-free resolver: one fixed policy, order-independent, never ranks
# ================================================

_OUTCOME_KIND = st.sampled_from(["complete", "candidate", "blocked", "not_applicable"])


def _outcomes(kinds: list[str]) -> dict[str, StrategyOutcome]:
    return {
        f"s{i}": StrategyOutcome(strategy=f"s{i}", leaf=f"leaf-{i}", outcome=kind)  # type: ignore[arg-type]
        for i, kind in enumerate(kinds)
    }


@given(st.lists(_OUTCOME_KIND, min_size=0, max_size=7))
def test_resolver_follows_the_fixed_policy(kinds: list[str]) -> None:
    result = ScoreFreeViabilityResolver().evaluate(_outcomes(kinds)).result
    completes = kinds.count("complete")
    viable = completes + kinds.count("candidate")
    if completes == 1 and viable == 1:
        expected = "complete"
    elif viable >= 1:
        expected = "needs_input"
    else:
        expected = "not_inferred"
    assert result == expected


@given(st.lists(_OUTCOME_KIND, min_size=1, max_size=7), st.randoms())
def test_resolver_is_order_independent(kinds: list[str], rng) -> None:
    shuffled = kinds[:]
    rng.shuffle(shuffled)
    a = ScoreFreeViabilityResolver().evaluate(_outcomes(kinds)).result
    b = ScoreFreeViabilityResolver().evaluate(_outcomes(shuffled)).result
    assert a == b


@given(st.integers(min_value=2, max_value=6))
def test_multiple_completes_are_a_decision_never_a_pick(count: int) -> None:
    # Several complete strategies must never resolve to a single automatic pick.
    result = ScoreFreeViabilityResolver().evaluate(_outcomes(["complete"] * count)).result
    assert result == "needs_input"


# ================================================
# resolve_logical_root: peeling invariants over generated trees
# ================================================


def _make_chain(root: Path, depth: int) -> Path:
    cur = root
    for i in range(depth):
        cur = cur / f"w{i}"
        cur.mkdir()
    return cur


@given(st.integers(min_value=0, max_value=6))
def test_single_child_chain_is_fully_peeled(depth: int) -> None:
    root = Path(tempfile.mkdtemp())
    try:
        leaf = _make_chain(root, depth)
        # Two meaningful entries at the leaf and no marker => the leaf is the root.
        (leaf / "main.py").write_text("x")
        (leaf / "other.py").write_text("y")
        expected = "." if depth == 0 else "/".join(f"w{i}" for i in range(depth))
        assert resolve_logical_root(root) == expected
    finally:
        shutil.rmtree(root)


@given(st.integers(min_value=0, max_value=6), st.sampled_from(["pyproject.toml", "Dockerfile", ".git"]))
def test_chain_stops_at_a_root_marker(depth: int, marker: str) -> None:
    root = Path(tempfile.mkdtemp())
    try:
        leaf = _make_chain(root, depth)
        (leaf / marker).write_text("x")  # a lone marker at the leaf
        expected = "." if depth == 0 else "/".join(f"w{i}" for i in range(depth))
        assert resolve_logical_root(root) == expected
    finally:
        shutil.rmtree(root)


@given(st.integers(min_value=1, max_value=5))
def test_result_always_names_an_existing_directory(depth: int) -> None:
    root = Path(tempfile.mkdtemp())
    try:
        leaf = _make_chain(root, depth)
        (leaf / "a.py").write_text("x")
        (leaf / "b.py").write_text("y")
        resolved = resolve_logical_root(root)
        target = root if resolved == "." else root / resolved
        assert target.is_dir()
    finally:
        shutil.rmtree(root)


# ================================================
# End-to-end build inference: determinism + the automatic-allowed invariant
# ================================================


def _make_build_tree(root: Path, *, has_docker: bool, has_req: bool, wrapped: bool) -> None:
    base = root / "proj-main" if wrapped else root
    base.mkdir(parents=True, exist_ok=True)
    (base / "main.py").write_text("print(1)\n")
    if has_docker:
        (base / "Dockerfile").write_text("FROM python:3.11-slim\n")
    if has_req:
        (base / "requirements.txt").write_text("pandas\n")


@given(st.booleans(), st.booleans(), st.booleans())
def test_build_inference_is_deterministic_and_automatic_is_safe(has_docker: bool, has_req: bool, wrapped: bool) -> None:
    dir_a = Path(tempfile.mkdtemp())
    dir_b = Path(tempfile.mkdtemp())
    try:
        _make_build_tree(dir_a, has_docker=has_docker, has_req=has_req, wrapped=wrapped)
        _make_build_tree(dir_b, has_docker=has_docker, has_req=has_req, wrapped=wrapped)
        intent = ReeIntent(name="Demo REE")
        selectors = [ScriptTargetSelector(kind="build")]
        result_a = infer_scripts(dir_a, selectors, intent=intent).results[0]
        result_b = infer_scripts(dir_b, selectors, intent=intent).results[0]

        # Determinism: identical inputs render byte-identical candidate bodies.
        assert [c.body for c in result_a.candidates] == [c.body for c in result_b.candidates]

        # No candidate is ever an empty-bodied sentinel.
        assert all(c.body for c in result_a.candidates)

        # The automatic-allowed invariant: a complete/automatic build is exactly
        # one candidate with no blocking warning.
        if result_a.status == "complete" and result_a.application == "automatic_allowed":
            assert len(result_a.candidates) == 1
            assert not any(w.blocking for w in result_a.warnings)

        # not_inferred yields no candidate but always a complete trace.
        if result_a.status == "not_inferred":
            assert result_a.candidates == []
            assert result_a.decision.result_node
    finally:
        shutil.rmtree(dir_a)
        shutil.rmtree(dir_b)


# ================================================
# Activation / experiment scaffolds: fail-closed and injection-safe
# ================================================

# Values a hostile repository could put in a filename, wrapper directory, or
# image tag. All are relative (no "/" leading, no "..") so they survive path
# validation and reach the shell renderers.
_NASTY = [
    'evil"; rm -rf / ; echo "',
    "evil`reboot`",
    "evil$(reboot)",
    "evil' ; reboot ; '",
    "with spaces and $HOME",
    "tab\tand:colon",
]


def _docker_activation_body(root: Path, runtime_path: str, image_tag: str) -> str:
    intent = ReeIntent(name="Demo", runtime=runtime_path)
    inputs = RuntimeInputs(
        declared_runtime_path=runtime_path,
        accessor=MemoryAccessor({runtime_path: docker_archive([image_tag], cmd=["python", "main.py"])}),
    )
    report = infer_scripts(root, [ScriptTargetSelector(kind="activation_run")], intent=intent, runtime_inputs=inputs)
    body = report.results[0].candidates[0].body
    assert body is not None
    return body


def _sh_parses(body: str) -> bool:
    # `sh -n` parses without executing: broken quoting is a syntax error here.
    return subprocess.run(["sh", "-n"], input=body, text=True, capture_output=True).returncode == 0


@pytest.mark.parametrize("tag", _NASTY)
def test_adversarial_image_tag_cannot_break_the_scaffold(tmp_path: Path, tag: str) -> None:
    (tmp_path / "Dockerfile").write_text("FROM x\n")
    body = _docker_activation_body(tmp_path, ".repo2ree/artifacts/runtime.tar", tag)
    assert _sh_parses(body), body
    # `reboot` must never appear as an executable token, only inside a quoted literal.
    assert "\nreboot\n" not in body


@pytest.mark.parametrize("suffix", _NASTY)
def test_adversarial_runtime_path_cannot_break_the_scaffold(tmp_path: Path, suffix: str) -> None:
    (tmp_path / "Dockerfile").write_text("FROM x\n")
    runtime_path = f".repo2ree/{suffix}.tar"
    body = _docker_activation_body(tmp_path, runtime_path, "ree-runtime:demo")
    assert _sh_parses(body), body


@given(st.sampled_from(["activation_run", "experiment_run"]), st.booleans())
def test_every_run_scaffold_is_fail_closed(kind: Literal["activation_run", "experiment_run"], docker: bool) -> None:
    root = Path(tempfile.mkdtemp())
    try:
        (root / "Dockerfile").write_text("FROM x\n")
        (root / "requirements.txt").write_text("flask\n")
        runtime = ".repo2ree/artifacts/runtime.tar" if docker else ".repo2ree/artifacts/runtime-venv.tar.gz"
        archive = docker_archive(["ree-runtime:demo"]) if docker else _venv_bytes()
        experiments = [_exp()] if kind == "experiment_run" else []
        intent = ReeIntent(name="Demo", runtime=runtime, experiments=experiments)
        inputs = RuntimeInputs(
            declared_runtime_path=runtime, experiments=experiments, accessor=MemoryAccessor({runtime: archive})
        )
        selector = ScriptTargetSelector(kind=kind, experiment_name="run" if experiments else None)
        result = infer_scripts(root, [selector], intent=intent, runtime_inputs=inputs).results[0]
        body = result.candidates[0].body
        assert body is not None
        # Fail-closed: an empty `set --`, a guard, and exit 64 when unconfigured.
        assert "set --\n" in body
        assert "exit 64" in body
        assert _sh_parses(body)
    finally:
        shutil.rmtree(root)


def _venv_bytes() -> bytes:
    archive: bytes = venv_archive()
    return archive


# ================================================
# Venv restore-dir recovery: only ever a safe, absolute, reconciled path
# ================================================

_DIR_NAME = st.text(alphabet="abcdefghijkmnp-_", min_size=1, max_size=12)


@given(_DIR_NAME, st.text(alphabet="abcdefghijkmnp-_/", min_size=1, max_size=20), st.booleans())
def test_recovered_venv_restore_dir_is_absolute_and_reconciled(top_dir: str, target: str, absolute: bool) -> None:
    # A venv bakes absolute paths, so a recovered restore dir must be absolute
    # AND its basename must equal the archive's own top directory — otherwise the
    # `tar -C <parent>` restore would not land there. Anything else -> None.
    prefix = "/" if absolute else ""
    command = f"/usr/bin/python3 -m venv {prefix}{target}"
    inspection = inspect_runtime_artifact(io.BytesIO(venv_archive(top_dir=top_dir, command=command)))
    assert isinstance(inspection, VenvArchiveInspection)
    if inspection.restore_dir is not None:
        assert inspection.restore_dir.startswith("/")
        assert PurePosixPath(inspection.restore_dir).name == top_dir


def _exp():
    from repo2ree_core.experiment import Experiment

    return Experiment(name="run", output_paths=["results/run.log"])
