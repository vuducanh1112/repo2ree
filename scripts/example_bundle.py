#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from repo2ree_assurance_checker.check import check as judge
from repo2ree_assurance_checker.files import load_spec
from repo2ree_assurance_checker.sources import read_git_history

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "test-artifacts" / "e2e"
STAGED = ROOT / "test-artifacts" / "example-bundle" / "ree-hello-world.zip"
EXAMPLE = ROOT / "examples" / "rees" / "ree-hello-world.zip"
TEST = "test-python-docker-authoring--test-the-example-ree-"
NAME = "ree-hello-world"


def authored(runs: Path = RUNS) -> Path:
    found = sorted(
        runs.glob(f"showcase-cli-*/tests/{TEST}*/artifacts/archives/sealed-*.zip"),
        key=lambda path: path.stat().st_mtime,
    )
    if not found:
        raise SystemExit(f"no command-line showcase run under {runs} sealed the Python Docker REE")
    return found[-1]


def named(bundle: Path) -> str | None:
    with zipfile.ZipFile(bundle) as archive:
        document = json.loads(archive.read("ree/ree.json"))
    name = document.get("subject", {}).get("definition", {}).get("name")
    return name if isinstance(name, str) else None


def stage(runs: Path = RUNS, staged: Path = STAGED) -> Path:
    bundle = authored(runs)
    if (name := named(bundle)) != NAME:
        raise SystemExit(f"{bundle} is the REE {name!r}, not {NAME!r}")
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bundle, staged)
    print(f">> staged {bundle.relative_to(runs)} as {staged}")
    return staged


def check(bundle: Path) -> list[str]:
    spec = load_spec()
    with tempfile.TemporaryDirectory(prefix="repo2ree-example-") as directory:
        with zipfile.ZipFile(bundle) as archive:
            archive.extractall(directory)
        root = Path(directory) / "ree"
        reviewed = any((root / "reviews").glob("*/review.json"))
        unsigned = {
            f"document:{rule.id}"
            for rules in spec.documents.values()
            for rule in rules.rules
            if (rule.pattern == "signature" and not any((root / (rule.files or "")).glob("*")))
            or (rules.reviews is not None and not reviewed)
        } | {f"aggregate:{name}" for name, aggregate in spec.aggregates.items() if aggregate.reviews and not reviewed}
        result = judge(spec, read_git_history(root, NAME, ree=NAME))
    problems = [
        f"{rule.rule} {rule.verdict}: "
        + "; ".join(f"{finding.subject} {finding.reason}" for finding in rule.findings[:3])
        for rule in result.rules
        if rule.verdict in {"violated", "inconclusive"}
    ]
    problems += [
        f"{rule.rule} judged nothing"
        for rule in result.rules
        if rule.kind in {"aggregate", "document"} and not rule.triggered and rule.rule not in unsigned
    ]
    return problems


def adopt(staged: Path = STAGED, example: Path = EXAMPLE) -> None:
    if not staged.is_file():
        raise SystemExit(f"nothing is staged at {staged}: run `just author-example-bundle` first")
    if problems := check(staged):
        raise SystemExit(
            "the staged bundle breaks the specification; the example is unchanged:\n" + "\n".join(problems)
        )
    shutil.copyfile(staged, example)
    print(f">> {example} is the bundle the showcase sealed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("stage", "adopt"))
    args = parser.parse_args(argv)
    if args.command == "stage":
        stage()
    else:
        adopt()
    return 0


if __name__ == "__main__":
    sys.exit(main())
