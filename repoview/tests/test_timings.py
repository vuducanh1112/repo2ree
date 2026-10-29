import json
from pathlib import Path
from typing import Any

from repo2ree_repoview.overview.pages.recipes import seconds, took
from repo2ree_repoview.overview.timings import SCHEMA, read_invocations, summarize


def invocation(logs: Path, name: str, start: dict[str, Any], *lines: Any) -> None:
    path = logs / "2026-10-29" / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    first = {"schema": SCHEMA, "kind": "start", "invocation": name, "argv": [], "machine": "local"} | start
    path.write_text("".join((line if isinstance(line, str) else json.dumps(line)) + "\n" for line in (first, *lines)))


def recipe(name: str, seconds: float) -> dict[str, Any]:
    return {"kind": "recipe", "recipe": name, "seconds": seconds, "at": "2026-10-29T13:00:00Z"}


def end(exit_code: int, seconds: float) -> dict[str, Any]:
    return {"kind": "end", "exit": exit_code, "seconds": seconds}


def test_invocations_are_read_as_recorded_and_what_this_build_cannot_read_is_skipped(tmp_path: Path) -> None:
    invocation(
        tmp_path, "a", {"argv": ["commit-gate"], "started": "2026-10-29T10:00:00Z"}, recipe("check", 27), end(0, 30)
    )
    # Interrupted: no end line; and a line this build cannot read.
    invocation(tmp_path, "b", {"argv": ["test-unit"], "started": "2026-10-29T11:00:00Z"}, "{torn", recipe("check", 1))
    (tmp_path / "2026-10-29" / "c.jsonl").write_text(json.dumps(recipe("orphan", 9)) + "\n")  # no start
    invocation(tmp_path, "d", {"schema": "repo2ree-just-timing/0", "started": "2026-10-29T12:00:00Z"})

    found = read_invocations(tmp_path)

    assert [(item.command, item.end is not None) for item in found] == [("commit-gate", True), ("test-unit", False)]
    assert [completed.seconds for completed in found[1].recipes] == [1.0]


def test_timings_are_medians_per_recipe_and_machine_with_the_last_run_beside_them(tmp_path: Path) -> None:
    gate = {"argv": ["commit-gate"], "revision": "aaaaaaaa1"}
    invocation(tmp_path, "1", gate | {"started": "2026-10-29T10:00:00Z"}, recipe("test-unit-package", 116), end(0, 143))
    invocation(tmp_path, "2", gate | {"started": "2026-10-29T11:00:00Z"}, recipe("test-unit-package", 64), end(0, 88))
    invocation(
        tmp_path,
        "3",
        gate | {"started": "2026-10-29T12:00:00Z", "revision": "bbbbbbbb2"},
        recipe("test-unit-package", 62),
        end(1, 87),
    )
    invocation(
        tmp_path,
        "4",
        {"argv": ["commit-gate"], "machine": "vm", "started": "2026-10-29T12:30:00Z"},
        recipe("test-unit-package", 40),
    )

    timings = summarize(read_invocations(tmp_path))

    local = timings.recipes["test-unit-package"]["local"]
    assert (local.runs, local.median, local.last, local.last_revision, local.last_exit) == (3, 64, 62, "bbbbbbbb2", 1)
    assert timings.recipes["test-unit-package"]["vm"].runs == 1
    # Only invocations that ended have a wall time.
    assert set(timings.commands["commit-gate"]) == {"local"}
    assert timings.commands["commit-gate"]["local"].median == 88
    assert timings.invocations == 4


def test_a_recipe_shows_each_machines_median_and_how_it_was_measured_on_hover(tmp_path: Path) -> None:
    invocation(tmp_path, "1", {"argv": ["x"], "revision": "cafef00d99", "started": "1"}, recipe("x", 61.9), end(2, 62))
    cell = took(summarize(read_invocations(tmp_path)).recipes["x"])
    assert ">local 62 s<" in cell
    assert 'title="median of 1 run; last 62 s at cafef00d, exit 2"' in cell
    assert "not recorded" in took({})
    assert (seconds(4.25), seconds(87.4), seconds(376)) == ("4.2 s", "87 s", "6.3 min")
