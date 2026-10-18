from __future__ import annotations

from scripts.check_spec_isolation import conflicts, main


def test_a_specification_change_with_its_generated_module_and_checker_is_allowed() -> None:
    assert (
        main(
            [
                "specifications/behaviour/entities/run.toml",
                "protocol/src/repo2ree_protocol/behaviour/machines.py",
                "conformance/src/repo2ree_conformance/check.py",
                "conformance/tests/test_check.py",
            ]
        )
        == 0
    )


def test_implementation_alone_is_allowed() -> None:
    assert main(["api/src/repo2ree_api/storage/json_run_store.py", "api/tests/unit/test_run_behaviour.py"]) == 0


def test_specification_and_runtime_together_are_refused() -> None:
    paths = ["specifications/behaviour/invariants.toml", "core/src/repo2ree_core/operations/capture.py"]
    assert conflicts(paths) == (paths[:1], paths[1:])
    assert main(paths) == 1
