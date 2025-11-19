import re
import ast
import configparser
from pathlib import Path
from datetime import datetime

from repo2ree.python_packages_util.pin_pypi_package_version import get_pypi_package_info

from packaging.specifiers import SpecifierSet
import tomli
import yaml

###################
# Main Functions
###################


def find_required_python_version(
    repo_dir: Path, cutoff_date: datetime
) -> SpecifierSet | None:
    required_python_version: SpecifierSet | None = None

    for func in [
        get_required_python_from_pyproject,
        get_required_python_from_poetry,
        get_required_python_from_environment_yml,
        get_required_python_from_runtime,
        get_required_python_from_setupcfg,
        get_required_python_from_setuppy,
    ]:
        required_python_version = func(repo_dir)
        if required_python_version:
            break

    return required_python_version


###################
# Impure Functions
###################


def extract_python_version_from_packages(
    pypi_packages: list, anaconda_packages: list
) -> SpecifierSet | None:
    pypi_infos = []
    for package in pypi_packages:
        try:
            pypi_info = get_pypi_package_info(package)
            pypi_infos.append(pypi_info)
        except Exception:
            continue


def find_declared_python_version(repo_dir: Path) -> SpecifierSet | None:
    for func in [
        get_required_python_from_pyproject,
        get_required_python_from_poetry,
        get_required_python_from_environment_yml,
        get_required_python_from_runtime,
        get_required_python_from_setupcfg,
        get_required_python_from_setuppy,
    ]:
        result = func(repo_dir)
        if result:
            return result


def get_required_python_from_pyproject(repo_dir: Path) -> SpecifierSet | None:
    pyproject_file = repo_dir / "pyproject.toml"
    if pyproject_file.exists():
        with open(pyproject_file, "rb") as f:
            data = tomli.load(f)
        version = data.get("project", {}).get("requires-python")
        if version:
            return SpecifierSet(version)
    return None


def get_required_python_from_poetry(repo_dir: Path) -> SpecifierSet | None:
    pyproject_file = repo_dir / "pyproject.toml"
    if pyproject_file.exists():
        with open(pyproject_file, "rb") as f:
            data = tomli.load(f)
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        python_version = poetry_deps.get("python")
        if python_version:
            if python_version.startswith("~") and not python_version.startswith(
                ("~=", "~>")
            ):
                python_version = "~=" + python_version.lstrip("~")
            return SpecifierSet(str(python_version))
    return None


def get_required_python_from_environment_yml(repo_dir: Path) -> SpecifierSet | None:
    env_file = repo_dir / "environment.yml"
    if env_file.exists():
        try:
            with open(env_file, "r") as f:
                env_data = yaml.safe_load(f)
            deps = env_data.get("dependencies", [])
            for dep in deps:
                if isinstance(dep, str) and dep.startswith("python"):
                    match = re.match(r"python([=><!~]+.+)", dep)
                    if match:
                        version_spec = match.groups()[0]
                        if version_spec.startswith("=") and not version_spec.startswith(
                            ("==", ">=", "<=", "!=")
                        ):
                            version_spec = "==" + version_spec.lstrip("=")
                        return SpecifierSet(version_spec)
        except Exception:
            pass
    return None


def get_required_python_from_runtime(repo_dir: Path) -> SpecifierSet | None:
    runtime_file = repo_dir / "runtime.txt"
    if runtime_file.exists():
        try:
            content = runtime_file.read_text().strip()
            match = re.search(r"python-([0-9]+\.[0-9]+(?:\.[0-9]+)?)", content)
            if match:
                return SpecifierSet(f"=={match.group(1)}")
        except Exception:
            pass
    return None


def get_required_python_from_setupcfg(repo_dir: Path) -> SpecifierSet | None:
    setupcfg_file = repo_dir / "setup.cfg"
    if setupcfg_file.exists():
        try:
            config = configparser.ConfigParser()
            config.read(setupcfg_file)
            if "options" in config and "python_requires" in config["options"]:
                version = config["options"]["python_requires"].strip()
                if version:
                    return SpecifierSet(version)
        except Exception:
            pass
    return None


def get_required_python_from_setuppy(repo_dir: Path) -> SpecifierSet | None:
    setuppy_file = repo_dir / "setup.py"
    if setuppy_file.exists():
        try:
            content = setuppy_file.read_text()
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "setup"
                ):
                    for keyword in node.keywords:
                        if keyword.arg == "python_requires":
                            if isinstance(keyword.value, ast.Constant):
                                version = keyword.value.value
                                if version:
                                    return SpecifierSet(str(version))
        except Exception:
            pass
    return None
