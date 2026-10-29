import json
import re
import subprocess
from typing import Any

import pytest
from packaging.markers import Marker
from scripts import closures

DOCUMENT = json.loads(closures.OUTPUT.read_text(encoding="utf-8"))


def test_the_committed_closures_are_current() -> None:
    assert closures.OUTPUT.read_text(encoding="utf-8") == closures.render(), "run: just generate-closures"


@pytest.mark.parametrize("name", sorted(DOCUMENT["closures"]))
@pytest.mark.parametrize("system", sorted(closures.SYSTEMS))
def test_a_closure_is_what_uv_exports(name: str, system: str) -> None:
    closure = DOCUMENT["closures"][name]
    exported = subprocess.run(
        ["uv", "export", "--frozen", "--no-dev", "--no-hashes", "--no-emit-workspace", "--package", closure["root"]],
        capture_output=True,
        text=True,
        check=True,
        cwd=closures.ROOT,
    ).stdout
    environment = closures.environment(closures.SYSTEMS[system])
    expected = set()
    for line in exported.splitlines():
        if not line or line.startswith(("#", " ")):
            continue
        requirement, _, marker = line.partition(";")
        if marker.strip() and not Marker(marker.strip()).evaluate(environment):
            continue
        name_part, _, version = requirement.partition("==")
        expected.add((re.sub(r"\[.*\]", "", name_part).strip().lower(), version.strip()))

    assert {(wheel["name"], wheel["version"]) for wheel in closure["systems"][system]} == expected


def lock(*packages: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {package["name"]: package for package in packages}


def wheel(filename: str) -> dict[str, str]:
    return {"url": f"https://files.example/{filename}", "hash": "sha256:" + "0" * 64}


def test_a_compiled_wheel_for_the_system_wins_over_a_pure_one() -> None:
    package = {
        "wheels": [
            wheel("demo-1.0-py3-none-any.whl"),
            wheel("demo-1.0-cp313-cp313-musllinux_1_2_x86_64.whl"),
            wheel("demo-1.0-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"),
            wheel("demo-1.0-cp313-cp313-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"),
        ]
    }

    chosen = closures.best_wheel(package, closures.supported_tags("x86_64"))

    assert chosen is not None
    assert chosen["url"].endswith("manylinux_2_17_x86_64.manylinux2014_x86_64.whl")


def test_a_wheel_needing_a_newer_glibc_is_never_chosen() -> None:
    package = {"wheels": [wheel("demo-1.0-cp313-cp313-manylinux_2_99_x86_64.whl")]}

    assert closures.best_wheel(package, closures.supported_tags("x86_64")) is None


def test_a_dependency_for_another_platform_is_not_reached() -> None:
    packages = lock(
        {
            "name": "app",
            "source": {"editable": "app"},
            "dependencies": [
                {"name": "colorama", "marker": "sys_platform == 'win32'"},
                {"name": "rich", "extra": ["jupyter"]},
            ],
        },
        {"name": "colorama", "source": {"registry": "x"}},
        {"name": "rich", "source": {"registry": "x"}, "optional-dependencies": {"jupyter": [{"name": "ipywidgets"}]}},
        {"name": "ipywidgets", "source": {"registry": "x"}},
    )

    assert closures.reached(packages, "app", "x86_64") == {"app", "rich", "ipywidgets"}


def test_a_package_without_a_wheel_for_a_system_is_refused() -> None:
    packages = lock(
        {"name": "app", "source": {"editable": "app"}, "dependencies": [{"name": "native"}]},
        {
            "name": "native",
            "version": "1.0",
            "source": {"registry": "x"},
            "wheels": [wheel("native-1.0-cp313-cp313-manylinux_2_17_x86_64.whl")],
        },
    )

    with pytest.raises(ValueError, match=re.escape("native 1.0 has no wheel for aarch64-linux")):
        closures.closure(packages, "app")
