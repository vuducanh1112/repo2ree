from pathlib import Path

from scripts.config.check import (
    EnvironmentReference,
    _declared,
    docker_environment_references,
    embedded_shell_environment_references,
    forbidden_workflow_environment,
    nix_environment_references,
    python_environment_references,
    typescript_environment_references,
)


def _names(references: set[EnvironmentReference]) -> set[str]:
    return {reference.name for reference in references}


def test_python_scanner_finds_reads_writes_and_embedded_shell(tmp_path: Path) -> None:
    source = tmp_path / "template.py"
    source.write_text(
        "import os\n"
        'os.environ.get("READ_ME")\n'
        'os.getenv("ALSO_READ")\n'
        'os.environ.setdefault("DEFAULT_ME", "1")\n'
        'os.environ["WRITE_ME"] = "yes"\n'
        'template = "${GENERATED_INPUT:-0}"\n'
    )

    references = python_environment_references(source) | embedded_shell_environment_references(source)

    assert _names(references) == {
        "ALSO_READ",
        "DEFAULT_ME",
        "GENERATED_INPUT",
        "READ_ME",
        "WRITE_ME",
    }


def test_typescript_scanner_ignores_vite_builtins(tmp_path: Path) -> None:
    source = tmp_path / "config.ts"
    source.write_text("process.env.E2E_BASE_URL;\nimport.meta.env.VITE_BUILD_REVISION;\nimport.meta.env.DEV;\n")

    assert _names(typescript_environment_references(source)) == {"E2E_BASE_URL", "VITE_BUILD_REVISION"}


def test_docker_scanner_finds_build_arguments(tmp_path: Path) -> None:
    source = tmp_path / "Dockerfile"
    source.write_text("ARG REPO2REE_BUILD_REVISION=development\nRUN echo ${PATH}\n")

    assert _names(docker_environment_references(source)) == {"PATH", "REPO2REE_BUILD_REVISION"}


def test_nix_scanner_finds_environment_reads(tmp_path: Path) -> None:
    source = tmp_path / "module.nix"
    source.write_text('let token = builtins.getEnv "DEPLOY_TOKEN"; in "${token}"\n')

    assert _names(nix_environment_references(source)) == {"DEPLOY_TOKEN"}


def test_declared_environment_patterns_cover_generated_tool_names() -> None:
    import re

    patterns = (re.compile(r"^REPO2REE_TOOL_[A-Z0-9_]+$"),)

    assert _declared("REPO2REE_TOOL_GIT_LFS", set(), patterns)
    assert not _declared("REPO2REE_UNKNOWN", set(), patterns)


def test_workflow_environment_is_rejected() -> None:
    contract = {
        "variables": {
            "RUNTIME_SETTING": {"kind": "runtime"},
            "WORKFLOW_SWITCH": {"kind": "workflow"},
        }
    }

    assert forbidden_workflow_environment(contract) == ["WORKFLOW_SWITCH"]
