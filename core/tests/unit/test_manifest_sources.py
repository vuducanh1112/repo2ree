"""Parse coverage for the first-party manifest sources.

Each format parser is pinned with representative input; ``scan_manifest_files``
is exercised end-to-end over a tmp repo, including the lock-merge and the
profiler-level report it feeds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.repo_profiler.profiler import AnalysisError, analyze_repo
from repo2ree_core.repo_profiler.sources.conda import parse_environment_yml
from repo2ree_core.repo_profiler.sources.manifests import merge_locked, scan_manifest_files
from repo2ree_core.repo_profiler.sources.npm import parse_package_json, parse_package_lock
from repo2ree_core.repo_profiler.sources.oci import parse_dockerfile
from repo2ree_core.repo_profiler.sources.pypi import (
    parse_poetry_lock,
    parse_pyproject,
    parse_requirements_txt,
    parse_uv_lock,
)

# --------------------------------------------------------------------------- #
# requirements.txt
# --------------------------------------------------------------------------- #


class TestRequirementsTxt:
    def test_constraint_shapes(self) -> None:
        text = "flask\nrequests==2.31.0\nnumpy>=1.20  # comment\n"
        deps = parse_requirements_txt(text, "requirements.txt")
        assert [(d.name, d.declared_constraint) for d in deps] == [
            ("flask", None),
            ("requests", "==2.31.0"),
            ("numpy", ">=1.20"),
        ]
        assert all(d.ecosystem == "pypi" and d.direct for d in deps)
        assert all(d.declared_in == "requirements.txt" for d in deps)

    def test_options_urls_and_paths_skipped(self) -> None:
        text = "-r base.txt\n--index-url https://x\ngit+https://github.com/x/y\n./local\nflask\n"
        deps = parse_requirements_txt(text, "requirements.txt")
        assert [d.name for d in deps] == ["flask"]

    def test_extras_and_markers_stripped(self) -> None:
        deps = parse_requirements_txt('uvicorn[standard]>=0.30; sys_platform != "win32"\n', "r.txt")
        (dep,) = deps
        assert (dep.name, dep.declared_constraint) == ("uvicorn", ">=0.30")

    def test_hash_mode_is_a_lock(self) -> None:
        text = "requests==2.31.0 \\\n    --hash=sha256:aaaa \\\n    --hash=sha256:bbbb\n"
        (dep,) = parse_requirements_txt(text, "requirements.txt")
        assert dep.declared_constraint == "==2.31.0"
        assert dep.locked_version == "2.31.0"
        assert dep.locked_hashes == ["sha256:aaaa", "sha256:bbbb"]
        assert dep.locked_in == "requirements.txt"

    def test_name_normalized(self) -> None:
        (dep,) = parse_requirements_txt("Typing_Extensions==4.1\n", "r.txt")
        assert dep.name == "typing-extensions"
        assert dep.name_as_written == "Typing_Extensions"


# --------------------------------------------------------------------------- #
# pyproject.toml
# --------------------------------------------------------------------------- #


class TestPyproject:
    def test_pep621_dependencies(self) -> None:
        text = '[project]\nname = "x"\ndependencies = ["pandas==2.1.0", "rich>=13; extra == \'cli\'"]\n'
        deps = parse_pyproject(text, "pyproject.toml")
        assert [(d.name, d.declared_constraint) for d in deps] == [
            ("pandas", "==2.1.0"),
            ("rich", ">=13"),
        ]

    def test_poetry_table_skips_python(self) -> None:
        text = (
            "[tool.poetry.dependencies]\n"
            'python = "^3.11"\n'
            'pandas = "==2.1.0"\n'
            'torch = { version = ">=2.0", source = "pytorch" }\n'
        )
        deps = parse_pyproject(text, "pyproject.toml")
        assert [(d.name, d.declared_constraint) for d in deps] == [
            ("pandas", "==2.1.0"),
            ("torch", ">=2.0"),
        ]

    def test_invalid_toml_is_empty(self) -> None:
        assert parse_pyproject("not [valid", "pyproject.toml") == []


# --------------------------------------------------------------------------- #
# environment.yml
# --------------------------------------------------------------------------- #


class TestEnvironmentYml:
    def test_conda_and_pip_entries(self) -> None:
        text = (
            "name: research\n"
            "dependencies:\n"
            "  - python=3.11\n"
            "  - numpy=1.21\n"
            "  - scipy\n"
            "  - pip:\n"
            "    - requests==2.31.0\n"
        )
        deps = parse_environment_yml(text, "environment.yml")
        assert [(d.ecosystem, d.name, d.declared_constraint) for d in deps] == [
            ("conda", "numpy", "=1.21"),
            ("conda", "scipy", None),
            ("pypi", "requests", "==2.31.0"),
        ]

    def test_invalid_yaml_is_empty(self) -> None:
        assert parse_environment_yml(":\n  - {", "environment.yml") == []


# --------------------------------------------------------------------------- #
# package.json + npm locks
# --------------------------------------------------------------------------- #


class TestNpm:
    def test_package_json_collects_direct_declaration_sections(self) -> None:
        text = """{
          "dependencies": {"react": "^18.3.0", "@scope/lib": "1.2.3"},
          "devDependencies": {"vitest": "~2.0.0"},
          "optionalDependencies": {"fsevents": "2.3.3"},
          "peerDependencies": {"react-dom": ">=18"}
        }"""
        deps = parse_package_json(text, "package.json")
        assert [(d.name, d.declared_constraint, d.scope) for d in deps] == [
            ("react", "^18.3.0", None),
            ("@scope/lib", "1.2.3", None),
            ("vitest", "~2.0.0", "dev"),
            ("fsevents", "2.3.3", "optional"),
            ("react-dom", ">=18", "peer"),
        ]
        assert all(d.ecosystem == "npm" and d.direct and d.declared_in == "package.json" for d in deps)

    def test_package_json_repeated_and_blank_names(self) -> None:
        """A package named in several sections is one row (first section wins);
        a blank key is not a package and must not crash the parser."""
        text = """{
          "dependencies": {"react": "^18.3.0", "": "1.0"},
          "peerDependencies": {"react": ">=18"}
        }"""
        deps = parse_package_json(text, "package.json")
        assert [(d.name, d.declared_constraint, d.scope) for d in deps] == [("react", "^18.3.0", None)]

    def test_package_lock_repeated_resolutions_collapse(self) -> None:
        """v1 locks nest the same resolution under several parents; it is one
        closure row with the union of hashes. Blank keys are skipped."""
        v1 = """{"dependencies": {
          "a": {"version": "1.0", "dependencies": {"left-pad": {"version": "1.3.0", "integrity": "sha512-x"}}},
          "b": {"version": "1.0", "dependencies": {"left-pad": {"version": "1.3.0", "integrity": "sha512-y"}}},
          "": {"version": "9.9"}
        }}"""
        deps = parse_package_lock(v1, "package-lock.json")
        pads = [d for d in deps if d.name == "left-pad"]
        assert [(d.locked_version, sorted(d.locked_hashes)) for d in pads] == [("1.3.0", ["sha512-x", "sha512-y"])]
        assert {d.name for d in deps} == {"a", "b", "left-pad"}

    def test_package_lock_v3_and_v1_produce_closure_rows(self) -> None:
        v3 = """{"lockfileVersion": 3, "packages": {
          "": {"name": "app"},
          "node_modules/react": {"version": "18.3.1", "integrity": "sha512-react"},
          "node_modules/@scope/lib": {"version": "1.2.3", "integrity": "sha512-lib"}
        }}"""
        v1 = """{"dependencies": {"left-pad": {"version": "1.3.0", "integrity": "sha512-pad",
          "dependencies": {"repeat-string": {"version": "1.6.1"}}}}}"""
        assert [(d.name, d.locked_version, d.locked_hashes) for d in parse_package_lock(v3, "package-lock.json")] == [
            ("react", "18.3.1", ["sha512-react"]),
            ("@scope/lib", "1.2.3", ["sha512-lib"]),
        ]
        assert [(d.name, d.locked_version) for d in parse_package_lock(v1, "package-lock.json")] == [
            ("left-pad", "1.3.0"),
            ("repeat-string", "1.6.1"),
        ]
        assert all(
            not d.direct and d.locked_in == "package-lock.json" for d in parse_package_lock(v3, "package-lock.json")
        )

    def test_package_json_and_lock_merge_to_locked_score(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')
        (tmp_path / "package-lock.json").write_text(
            '{"lockfileVersion": 3, "packages": {"": {}, "node_modules/react": {"version": "18.3.1"}}}'
        )
        report = analyze_repo(tmp_path)
        assert report.dependency_level == 3
        assert [(d.ecosystem, d.name, d.locked_version) for d in report.dependencies] == [("npm", "react", "18.3.1")]


# --------------------------------------------------------------------------- #
# Dockerfile
# --------------------------------------------------------------------------- #


class TestDockerfile:
    def test_from_variants(self) -> None:
        text = (
            "FROM --platform=linux/amd64 python:3.11 AS build\n"
            "FROM ghcr.io/org/tool@sha256:abc\n"
            "FROM registry:5000/app:1.2\n"
            "FROM build\n"
            "FROM scratch\n"
            "FROM ${BASE}\n"
        )
        deps = parse_dockerfile(text, "Dockerfile")
        assert [(d.name, d.declared_constraint, d.locked_hashes) for d in deps] == [
            ("python", "3.11", []),
            ("ghcr.io/org/tool", None, ["sha256:abc"]),
            ("registry:5000/app", "1.2", []),
        ]
        assert all(d.ecosystem == "oci" and d.declared_in == "Dockerfile" for d in deps)

    def test_stage_aliases_make_parsing_stateful(self) -> None:
        """Dockerfile parsing is deliberately NOT line-local (unlike
        requirements.txt): a stage alias changes the meaning of later FROMs,
        so parse(A + B) != parse(A) + parse(B). Anyone unifying the parsers
        around line locality breaks multi-stage handling."""
        stage = "FROM python:3.11 AS build\n"
        use = "FROM build\n"
        assert [d.name for d in parse_dockerfile(stage + use, "Dockerfile")] == ["python"]
        # Parsed alone, `FROM build` is an image reference, not a stage.
        assert [d.name for d in parse_dockerfile(use, "Dockerfile")] == ["build"]


# --------------------------------------------------------------------------- #
# lockfiles
# --------------------------------------------------------------------------- #

_UV_LOCK = """
version = 1

[[package]]
name = "myproject"
version = "0.1.0"
source = { virtual = "." }

[[package]]
name = "requests"
version = "2.31.0"
source = { registry = "https://pypi.org/simple" }
sdist = { url = "https://x/requests.tar.gz", hash = "sha256:sdist" }
wheels = [
    { url = "https://x/requests.whl", hash = "sha256:wheel" },
]
"""

_POETRY_LOCK = """
[[package]]
name = "Typing_Extensions"
version = "4.10.0"
files = [
    {file = "typing_extensions.whl", hash = "sha256:whl"},
]
"""


class TestLockfiles:
    def test_uv_lock_skips_the_project_itself(self) -> None:
        (dep,) = parse_uv_lock(_UV_LOCK, "uv.lock")
        assert (dep.name, dep.locked_version) == ("requests", "2.31.0")
        assert dep.locked_hashes == ["sha256:sdist", "sha256:wheel"]
        assert dep.direct is False
        assert dep.locked_in == "uv.lock"

    def test_poetry_lock_normalizes_names(self) -> None:
        (dep,) = parse_poetry_lock(_POETRY_LOCK, "poetry.lock")
        assert (dep.name, dep.locked_version) == ("typing-extensions", "4.10.0")
        assert dep.locked_hashes == ["sha256:whl"]

    def test_forked_resolution_merges_hashes_across_forks(self) -> None:
        """Universal locks list the same package once per marker/platform fork;
        a declared row matched by several forks must keep every fork's hashes."""
        forked_lock = """
        version = 1

        [[package]]
        name = "numpy"
        version = "1.26.4"
        resolution-markers = ["python_full_version < '3.12'"]
        wheels = [{ url = "https://x/np1.whl", hash = "sha256:old" }]

        [[package]]
        name = "numpy"
        version = "2.0.0"
        resolution-markers = ["python_full_version >= '3.12'"]
        wheels = [{ url = "https://x/np2.whl", hash = "sha256:new" }]
        """
        declared = parse_requirements_txt("numpy\n", "requirements.txt")
        locked = parse_uv_lock(forked_lock, "uv.lock")
        assert len(locked) == 2  # both forks survive parsing

        (dep,) = merge_locked(declared, locked)
        assert dep.locked_version == "1.26.4"  # first fork is the representative
        assert dep.locked_hashes == ["sha256:old", "sha256:new"]  # union, in order


# --------------------------------------------------------------------------- #
# merge + end-to-end scan
# --------------------------------------------------------------------------- #


class TestMergeAndScan:
    def test_merge_fills_declared_rows_and_keeps_closure(self) -> None:
        declared = parse_requirements_txt("requests>=2\n", "requirements.txt")
        locked = parse_uv_lock(_UV_LOCK, "uv.lock")
        merged = merge_locked(declared, locked)
        (dep,) = merged  # the closure row matched, so no extra row remains
        assert dep.direct is True
        assert dep.declared_constraint == ">=2"
        assert dep.locked_version == "2.31.0"
        assert dep.locked_in == "uv.lock"

    def test_scan_locked_repo_reaches_locked_level(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("requests>=2\n")
        (tmp_path / "uv.lock").write_text(_UV_LOCK)
        (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
        (tmp_path / ".venv" / "sub").mkdir(parents=True)
        (tmp_path / ".venv" / "sub" / "requirements.txt").write_text("garbage==1\n")

        inventory = scan_manifest_files(tmp_path)
        names = {(d.ecosystem, d.name) for d in inventory.dependencies}
        assert names == {("pypi", "requests"), ("oci", "python")}

        report = analyze_repo(tmp_path)
        assert report.dependency_level == 3  # Locked
        assert report.environment_level == 1  # Container
        assert report.dependency_summary.total == 1
        assert "floating-base-image" in {t.id for t in report.threats}

    def test_scan_unpinned_repo_stays_declared(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask\n")
        report = analyze_repo(tmp_path)
        assert report.dependency_level == 1  # Declared
        assert {t.id for t in report.threats if t.category.value == "dependency"} == {"unpinned-deps"}

    def test_strict_fails_when_the_scan_finds_no_dependency_data(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").write_text("just prose\n")
        with pytest.raises(AnalysisError):
            analyze_repo(tmp_path, strict=True)

    def test_strict_passes_once_dependency_data_exists(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask==1.0\n")
        report = analyze_repo(tmp_path, strict=True)
        assert report.dependency_summary.total == 1

    def test_adding_files_under_skipped_dirs_changes_nothing(self, tmp_path: Path) -> None:
        """Metamorphic twin of the pruning rule: junk under any skipped
        directory must leave the whole report — inventory, signals, levels,
        threats — bit-identical."""
        (tmp_path / "requirements.txt").write_text("requests>=2\n")
        before = analyze_repo(tmp_path)

        for junk_dir in (".git", ".venv", "venv", "node_modules", "__pycache__"):
            d = tmp_path / junk_dir
            d.mkdir()
            (d / "requirements.txt").write_text("evil==1\n")
            (d / "Dockerfile").write_text("FROM evil:latest\n")
            (d / "default.nix").write_text("{}\n")
            (d / "machine.qcow2").write_bytes(b"\x00")

        assert analyze_repo(tmp_path) == before

    def test_vendored_manifests_are_not_the_repos_own(self, tmp_path: Path) -> None:
        """Pruned directories must not contribute file signals either: a
        node_modules package.json or a committed .venv requirements.txt would
        otherwise bump a manifest-less repo to Declared on garbage evidence."""
        (tmp_path / "node_modules" / "leftpad").mkdir(parents=True)
        (tmp_path / "node_modules" / "leftpad" / "package.json").write_text("{}")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "requirements.txt").write_text("garbage==1\n")

        report = analyze_repo(tmp_path)
        assert report.dependency_level == 0  # None — nothing declared by the repo
        assert report.dependency_summary.manifests == 0
        assert "no-manifest" in {t.id for t in report.threats}
