"""What the overview reads: the head, the certificates, the receipt's evidence, the excuses, the recipes, and the
specification and zones as their owners export them."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo2ree_repoview.repository import ROOT, git

CERTIFICATES = ROOT / ".validation-certificates"


EXPECTATIONS = ROOT / "conformance/expected-verdicts.toml"


DIAGRAMS = ROOT / "reports/diagrams"


OVERVIEWS = ROOT / "reports/overview"


ENVIRONMENT = ROOT / "contracts/config/environment.json"


OPENAPI = ROOT / "contracts/openapi.json"


@dataclass(frozen=True)
class Head:
    revision: str
    tree: str
    index_tree: str
    subject: str
    branch: str
    dirty: bool
    committed: str


def head() -> Head:
    return Head(
        revision=git("rev-parse", "HEAD"),
        tree=git("rev-parse", "HEAD^{tree}"),
        index_tree=git("write-tree"),
        subject=git("log", "-1", "--format=%s"),
        branch=git("rev-parse", "--abbrev-ref", "HEAD"),
        dirty=bool(git("status", "--porcelain")),
        committed=git("log", "-1", "--format=%cI"),
    )


@dataclass(frozen=True)
class Certificate:
    name: str
    recipe: str
    state: str  # current, stale, missing
    detail: str


def certificates(now: Head) -> tuple[list[Certificate], dict[str, Any] | None]:
    found: list[Certificate] = []
    commit = CERTIFICATES / "commit-gate-ok"
    if commit.is_file():
        tree = commit.read_text().strip()
        current = tree in {now.tree, now.index_tree}
        found.append(
            Certificate("Commit gate", "just commit-gate", "current" if current else "stale", f"tree {tree[:10]}")
        )
    else:
        found.append(Certificate("Commit gate", "just commit-gate", "missing", "never run in this clone"))
    receipt: dict[str, Any] | None = None
    behaviour = CERTIFICATES / "behaviour-ok"
    if behaviour.is_file():
        receipt = json.loads(behaviour.read_text())
        detail = f"{receipt.get('revision', '')[:10]}: {len(receipt.get('tests', []))} tests"
        if receipt.get("tree") != now.tree:
            state = "stale"
        elif now.dirty:
            state, detail = "current", detail + "; covers HEAD, not the uncommitted changes"
        else:
            state = "current"
        found.append(Certificate("Behaviour gate", "just behaviour-gate", state, detail))
    else:
        found.append(Certificate("Behaviour gate", "just behaviour-gate", "missing", "never run in this clone"))
    publish = CERTIFICATES / "publish-gate-ok"
    if publish.is_file():
        rows = dict(line.split("\t")[:2] for line in publish.read_text().splitlines() if line.count("\t") == 1)
        current = rows.get("tree") == now.tree
        detail = f"{rows.get('revision', '?')[:10]}: local image set"
        found.append(Certificate("Publish gate", "just publish-gate", "current" if current else "stale", detail))
    else:
        found.append(Certificate("Publish gate", "just publish-gate", "missing", "never run in this clone"))
    return found, receipt


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_name(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


class Bundle:
    """The overview's own copy of what it shows from outside the tree, and what it only references."""

    def __init__(self, root: Path, revision: str) -> None:
        self.root = root
        self.revision = revision
        self.copied: list[dict[str, Any]] = []
        self.referenced: list[dict[str, Any]] = []

    def copy(self, source: Path, target: str, **context: str) -> str | None:
        """Copy one file to ``target`` (relative to the bundle); None when the source is missing."""
        if not source.is_file():
            return None
        destination = self.root / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        self.copied.append({"path": target, "source": source_name(source), "sha256": sha256(destination), **context})
        return target

    def write(self, target: str, content: str, source: str, **context: str) -> None:
        """Keep a document an owner produced on request (``source`` is the command), as if copied."""
        destination = self.root / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        self.copied.append({"path": target, "source": source, "sha256": sha256(destination), **context})

    def copy_tree(self, source: Path, target: str, **context: str) -> None:
        for path in sorted(source.rglob("*")) if source.is_dir() else []:
            if path.is_file():
                self.copy(path, f"{target}/{path.relative_to(source)}", **context)

    def reference(self, source: Path, **context: str) -> None:
        for path in sorted(source.rglob("*")) if source.is_dir() else [source] if source.is_file() else []:
            if path.is_file():
                entry = {"source": source_name(path), "sha256": sha256(path), "bytes": path.stat().st_size}
                self.referenced.append(entry | context)


# What a test's evidence holds, by whether the overview copies it or only names it by hash.
COPIED = (
    "test.json",
    "junit.xml",
    "logs",
    "verification",
    "traces",
    "recording/manifest.json",
    "recording/journal",
    "recording/stores",
)


REFERENCED = ("recording/rees", "recording/telemetry", "artifacts")


def bundle_evidence(bundle: Bundle, receipt: dict[str, Any] | None) -> tuple[list[Path], dict[tuple[str, str], str]]:
    """Copy the receipt and its runs' evidence; (bundled run directories, (run, test) -> bundled test directory)."""
    if receipt is None:
        return [], {}
    bundle.copy(CERTIFICATES / "behaviour-ok", "evidence/behaviour-ok.json", kind="receipt")
    runs: list[Path] = []
    tests: dict[tuple[str, str], str] = {}
    for run in (ROOT / name for name in receipt.get("runs", [])):
        if not (run / "run.json").is_file():
            continue
        described = json.loads((run / "run.json").read_text())
        context = {"run": run.name, "run_revision": str(described.get("build_revision", ""))}
        bundle.copy(run / "run.json", f"evidence/{run.name}/run.json", **context)
        for test in described.get("tests", []):
            target = f"evidence/{run.name}/{test['directory']}"
            for part in COPIED:
                source = run / test["directory"] / part
                if source.is_dir():
                    bundle.copy_tree(source, f"{target}/{part}", **context)
                else:
                    bundle.copy(source, f"{target}/{part}", **context)
            for part in REFERENCED:
                bundle.reference(run / test["directory"] / part, **context)
            tests[(run.name, str(test["name"]))] = target
        runs.append(bundle.root / "evidence" / run.name)
    return runs, tests


def suite_coverage(runs: list[Path]) -> tuple[Counter[str], Counter[str]]:
    """(edge and message counts, rule trigger counts) over the bundled evidence of the receipt's tests."""
    edges: Counter[str] = Counter()
    rules: Counter[str] = Counter()
    for run in runs:
        for report in run.glob("tests/*/verification/conformance.json"):
            data = json.loads(report.read_text())
            for machine, counts in data.get("coverage", {}).get("transitions", {}).items():
                edges.update({f"{machine} {edge}": count for edge, count in counts.items()})
            for boundary, counts in data.get("coverage", {}).get("messages", {}).items():
                edges.update({f"{boundary}: {message}": count for message, count in counts.items()})
            rules.update({rule["rule"]: int(rule.get("triggered", 0)) for rule in data.get("rules", [])})
    return edges, rules


def suite_extras(runs: list[Path]) -> Counter[tuple[str, str]]:
    """What the receipt's tests recorded beyond the vocabulary, as each test's verdicts list it."""
    found: Counter[tuple[str, str]] = Counter()
    for run in runs:
        for report in run.glob("tests/*/verification/conformance.json"):
            for extra in json.loads(report.read_text()).get("extras", []):
                found[(extra["subject"], extra.get("fact") or "")] += int(extra["count"])
    return found


def excuses() -> tuple[list[dict[str, Any]], dict[str, str]]:
    declared = tomllib.loads(EXPECTATIONS.read_text())
    unreached = {item: entry["reason"] for entry in declared.get("unreached", []) for item in entry["items"]}
    return declared.get("expected", []), unreached


# The owners' exports the overview draws from, and the commands that produce them.
SPEC_EXPORT = (sys.executable, "-m", "repo2ree_conformance", "export")
ZONES_EXPORT = (sys.executable, "scripts/zones.py", "export")


def exported(command: tuple[str, ...]) -> str:
    return subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True).stdout


def recipes() -> list[dict[str, Any]]:
    dump = json.loads(
        subprocess.run(
            ["just", "--dump", "--dump-format", "json"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout
    )
    listed = []
    for name, raw in dump["recipes"].items():
        group = next(
            (a["group"] for a in raw.get("attributes", []) if isinstance(a, dict) and "group" in a), "Ungrouped"
        )
        listed.append(
            {
                "name": name,
                "group": group,
                "doc": raw.get("doc") or "",
                "private": bool(raw.get("private")),
                "parameters": [p["name"] for p in raw.get("parameters", [])],
                "dependencies": [d["recipe"] for d in raw.get("dependencies", [])],
            }
        )
    return sorted(listed, key=lambda r: (r["group"], r["name"]))
