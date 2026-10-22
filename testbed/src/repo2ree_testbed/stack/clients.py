"""The suites a stack serves: a Playwright project or a test script, each listing its tests and running them."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Protocol
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.records import Outcome
from repo2ree_testbed.stack.process import capture, free_port

GUI = ROOT / "gui"
PLAYWRIGHT = ("npm", "exec", "--", "playwright", "test", "-c", "playwright.config.ts")


@dataclass(frozen=True)
class TestCase:
    __test__ = False

    name: str
    slug: str
    selection: tuple[str, ...]


@dataclass(frozen=True)
class Launch:
    output: Path
    log: IO[bytes] | None
    test: str | None


class Started:
    def __init__(self, process: subprocess.Popen[bytes], status_file: Path | None = None) -> None:
        self.process = process
        self.status_file = status_file

    def poll(self) -> int | None:
        status = self.process.poll()
        if status is None or self.status_file is None:
            return status
        try:
            return int(self.status_file.read_text().strip())
        except (OSError, ValueError):
            return 1
        finally:
            self.status_file.unlink(missing_ok=True)


class Client(Protocol):
    @property
    def suite(self) -> str: ...

    def tests(self) -> list[TestCase]: ...

    def start(
        self, api_url: str, environment: Mapping[str, str], selection: Sequence[str], launch: Launch
    ) -> Started: ...

    def archive_dirs(self, output: Path) -> tuple[Path, ...]: ...


def slug(*parts: str) -> str:
    return "--".join(re.sub(r"[^a-z0-9]+", "-", part.lower()).strip("-") for part in parts if part)


def _popen(
    command: Sequence[str], cwd: Path, environment: Mapping[str, str], launch: Launch
) -> subprocess.Popen[bytes]:
    stderr = subprocess.STDOUT if launch.log else None
    return subprocess.Popen(list(command), cwd=cwd, env=dict(environment), stdout=launch.log, stderr=stderr)


class _Spec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    file: str
    line: int
    title: str


class _Suite(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    title: str = ""
    specs: tuple[_Spec, ...] = ()
    suites: tuple[_Suite, ...] = ()


class _Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    root: Path = Field(alias="rootDir")


class _Listing(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    config: _Config
    suites: tuple[_Suite, ...]


@dataclass(frozen=True)
class Playwright:
    project: str

    @property
    def suite(self) -> str:
        return self.project

    def tests(self) -> list[TestCase]:
        listing = _Listing.model_validate_json(
            capture([*PLAYWRIGHT, f"--project={self.project}", "--list", "--reporter=json"], cwd=GUI, check=True)
        )
        found: list[TestCase] = []

        def walk(suite: _Suite, titles: list[str]) -> None:
            for spec in suite.specs:
                location = f"{(listing.config.root / spec.file).relative_to(GUI)}:{spec.line}"
                stem = Path(spec.file).name.removesuffix(".spec.ts")
                name = " > ".join([spec.file, *titles, spec.title])
                found.append(TestCase(name, slug(stem, *titles, spec.title), (location,)))
            for child in suite.suites:
                walk(child, [*titles, child.title] if child.title and not child.title.endswith(".ts") else titles)

        for suite in listing.suites:
            walk(suite, [])
        return found

    def start(self, api_url: str, environment: Mapping[str, str], selection: Sequence[str], launch: Launch) -> Started:
        print(f">> stack ready — running playwright project={self.project}")
        env = {**environment, "E2E_API_BASE_URL": api_url}
        if launch.test:
            env["E2E_GUI_PORT"] = str(free_port())
        command = [*PLAYWRIGHT, f"--project={self.project}", "--output", str(launch.output), *selection]
        return Started(_popen(command, GUI, env, launch))

    def archive_dirs(self, output: Path) -> tuple[Path, ...]:
        return (output,)

    def accepts(self) -> str | None:
        probe = subprocess.run(
            [*PLAYWRIGHT, f"--project={self.project}", "--list"], cwd=GUI, check=False, capture_output=True, text=True
        )
        return probe.stdout + probe.stderr if probe.returncode else None


@dataclass(frozen=True)
class Script:
    path: Path
    record: Path | None = None

    @property
    def suite(self) -> str:
        return self.path.name

    def tests(self) -> list[TestCase]:
        cases = []
        for node in filter(None, capture([str(self.path), "--list"], check=True).splitlines()):
            path, _, name = node.partition("::")
            cases.append(TestCase(node, slug(Path(path).stem, name), (node,)))
        return cases

    def start(self, api_url: str, environment: Mapping[str, str], selection: Sequence[str], launch: Launch) -> Started:
        print(f">> stack ready — running script={self.path}")
        if self.record is None:
            command = [str(self.path), "--base-url", api_url, *selection]
            return Started(_popen(command, ROOT, environment, launch))
        self.record.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix="repo2ree-record-status-")
        os.close(descriptor)
        status = Path(name)
        session = (
            f"{shlex.quote(str(self.path))} --base-url {shlex.quote(api_url)}; "
            f"printf '%s\\n' $? > {shlex.quote(str(status))}"
        )
        return Started(
            subprocess.Popen(["asciinema", "rec", "--overwrite", "-c", session, str(self.record)], cwd=ROOT), status
        )

    def archive_dirs(self, output: Path) -> tuple[Path, ...]:
        return ()


def reported_outcome(report: Path, status: int) -> tuple[Outcome, str]:
    fallback: tuple[Outcome, str] = ("passed", "") if status == 0 else ("failed", "")
    try:
        case = ElementTree.parse(report).getroot().find(".//testcase")  # noqa: S314 - written by our own client
    except (OSError, ElementTree.ParseError):
        return fallback
    if case is None:
        return fallback
    tags: tuple[tuple[str, Outcome], ...] = (("failure", "failed"), ("error", "failed"), ("skipped", "skipped"))
    for tag, outcome in tags:
        found = case.find(tag)
        if found is not None:
            xfail = tag == "skipped" and found.get("type") == "pytest.xfail"
            return ("xfailed" if xfail else outcome), found.get("message", "")
    return fallback
