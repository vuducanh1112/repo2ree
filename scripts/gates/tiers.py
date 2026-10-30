#!/usr/bin/env python3
"""Tier receipts: a gated tier's run, certified from its own record, and the gates composed of them.

A tier run leaves evidence (``run.json``, written by the testbed); only this module turns it
into a receipt, judging the record as raw JSON so no testbed change can bend what it accepts.
``policy.toml`` says what each tier must have run with and what each gate requires.

- ``certify --tier T [--run DIR | --invocation ID] [--if-eligible]`` writes
  ``.receipts/tiers/<T>/<tree>-<os>-<arch>.json`` when the run qualifies: built from the clean
  tree still checked out, the whole tier, the policy's parameters, every test passed (skips
  only where the policy allows), and for a judged tier every test's behaviour passed or was
  excused, by the checker in this tree. ``--if-eligible`` reports a run that does not qualify
  and succeeds anyway, for recipes a developer runs.
- ``missing GATE --platforms P`` prints, as ``<tier> <recipe>``, each tier the gate needs
  that this machine could prove and has no current receipt for.
- ``require GATE --platforms P`` fails unless every tier receipt the gate needs is current.
- ``plan GATE --platforms P`` shows what is proven for HEAD and how to prove the rest.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.gates import assurance_gate, receipts
from scripts.gates.receipts import ReceiptError, TierReceipt

ROOT = Path(__file__).resolve().parents[2]
POLICY = Path(__file__).with_name("policy.toml")
RUNS = assurance_gate.RUNS


@dataclass(frozen=True)
class Tier:
    name: str
    recipe: str
    parameters: dict[str, Any]
    judged: bool
    skips: bool


@dataclass(frozen=True)
class GatePolicy:
    name: str
    gates: tuple[str, ...]
    tiers: dict[str, str]  # tier -> "any", "here", or "each"


@dataclass(frozen=True)
class Policy:
    tiers: dict[str, Tier]
    gates: dict[str, GatePolicy]


def load_policy(path: Path = POLICY) -> Policy:
    document = tomllib.loads(path.read_text())
    tiers = {
        name: Tier(
            name,
            str(entry["recipe"]),
            dict(entry.get("parameters", {})),
            bool(entry.get("judged", False)),
            bool(entry.get("skips", False)),
        )
        for name, entry in document.get("tiers", {}).items()
    }
    gates = {}
    for name, entry in document.get("gates", {}).items():
        wanted = dict(entry.get("tiers", {}))
        unknown = [tier for tier in wanted if tier not in tiers]
        if unknown or any(where not in {"any", "here", "each"} for where in wanted.values()):
            raise ValueError(f"{path}: gate {name} names an unknown tier or place: {wanted}")
        gates[name] = GatePolicy(name, tuple(entry.get("gates", ())), wanted)
    return Policy(tiers, gates)


def platform() -> str:
    """This machine's Docker platform, as a run record names it."""
    result = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


# ================================================
# Certifying one run
# ================================================


def run_problems(root: Path, record: dict[str, Any], tier: Tier, tree: str) -> list[str]:
    """Why the run in ``root`` does not certify ``tier`` on ``tree``; empty when it does."""
    problems = []
    if record.get("tier") != tier.name:
        problems.append(f"it is a {record.get('tier')!r} run, not {tier.name}")
    if not record.get("tree"):
        problems.append("it was built from a dirty tree, or one that changed while it ran")
    elif record["tree"] != tree:
        problems.append(f"it ran on tree {str(record['tree'])[:12]}, not HEAD's {tree[:12]}")
    if record.get("selected"):
        problems.append(f"it ran only the tests matching {' or '.join(record['selected'])}")
    parameters = record.get("parameters") or {}
    for key, wanted in tier.parameters.items():
        if parameters.get(key) != wanted:
            problems.append(f"it ran with {key}={parameters.get(key)!r}; the policy asks {wanted!r}")
    if not record.get("platform"):
        problems.append("it names no platform")
    tests = record.get("tests") or []
    if not tests:
        problems.append("it records no test")
    failed = [test["name"] for test in tests if test.get("outcome") not in {"passed", "skipped"}]
    problems += [f"{name} did not pass" for name in failed]
    if not tier.skips:
        problems += [f"{test['name']} was skipped" for test in tests if test.get("outcome") == "skipped"]
    if tier.judged and tests:
        expectations = assurance_gate.load_expectations()
        for judgement in assurance_gate.judge_runs([root], expectations):
            problems += [f"{judgement.test}: {problem}" for problem in judgement.problems]
    return problems


def runs_of(tier: str, invocation: str | None, run: Path | None) -> list[Path]:
    """The run to certify: the one given, or this tier's runs that name the invocation, newest first."""
    if run is not None:
        return [run.resolve()]
    if not invocation:
        return []
    found = assurance_gate.runs_of(invocation, RUNS)
    return sorted(
        (root for root in found if json.loads((root / "run.json").read_text()).get("tier") == tier), reverse=True
    )


def certify(tier: Tier, root: Path) -> TierReceipt:
    """The receipt for the run in ``root``; ReceiptError naming every reason it does not qualify."""
    revision, tree, problems = assurance_gate.clean_head()
    record = json.loads((root / "run.json").read_text())
    problems += run_problems(root, record, tier, tree)
    if problems:
        raise ReceiptError(f"{root.name} certifies nothing:\n  " + "\n  ".join(problems))
    tests = record["tests"]
    receipt = TierReceipt(
        revision=revision,
        tree=tree,
        written=receipts.now(),
        tier=tier.name,
        platform=record["platform"],
        machine=record.get("machine") or "local",
        run=str(root.relative_to(ROOT)) if root.is_relative_to(ROOT) else str(root),
        tests=len(tests),
        skipped=sum(test.get("outcome") == "skipped" for test in tests),
        judged=tier.judged,
    )
    receipts.write(receipts.tier_path(ROOT, tier.name, tree, receipt.platform), receipt)
    return receipt


# ================================================
# What a gate needs
# ================================================


@dataclass(frozen=True)
class Need:
    """One tier receipt a gate needs: the tier, and the platform (or "any")."""

    tier: str
    platform: str


def needs(gate: GatePolicy, platforms: list[str]) -> list[Need]:
    found = []
    for tier, where in gate.tiers.items():
        if where == "each":
            found += [Need(tier, wanted) for wanted in platforms]
        elif where == "here":
            found.append(Need(tier, platform()))
        else:
            found.append(Need(tier, "any"))
    return found


def current(need: Need, tree: str) -> TierReceipt | None:
    """A receipt that meets ``need`` on ``tree``, if one exists."""
    directory = ROOT / receipts.DIRECTORY / "tiers" / need.tier
    for path in sorted(directory.glob(f"{tree}-*.json")):
        try:
            receipt = receipts.read(TierReceipt, path)
        except ReceiptError:
            continue
        if receipt is not None and receipt.tree == tree and need.platform in {"any", receipt.platform}:
            return receipt
    return None


def latest(need: Need) -> TierReceipt | None:
    """The newest receipt for the tier on any tree: what a stale need last had."""
    directory = ROOT / receipts.DIRECTORY / "tiers" / need.tier
    found = []
    for path in directory.glob("*.json"):
        try:
            receipt = receipts.read(TierReceipt, path)
        except ReceiptError:
            continue
        if receipt is not None and need.platform in {"any", receipt.platform}:
            found.append(receipt)
    return max(found, key=lambda receipt: receipt.written, default=None)


def unmet(gate: GatePolicy, platforms: list[str], tree: str) -> list[Need]:
    return [need for need in needs(gate, platforms) if current(need, tree) is None]


def gate_policy(name: str) -> GatePolicy:
    policy = load_policy()
    if name not in policy.gates:
        raise SystemExit(f"no gate {name!r} in {POLICY}; known: {', '.join(policy.gates)}")
    return policy.gates[name]


def gate_holds(name: str, tree: str) -> bool:
    """Whether another gate's own proof stands for ``tree``: its receipt, or (zones) its check."""
    if name == "commit-gate":
        receipt = receipts.read(receipts.CommitGateReceipt, receipts.path(ROOT, "commit-gate"))
        return receipt is not None and receipt.tree == tree
    if name == "assurance-gate":
        return not assurance_gate.verify()
    if name == "zones-gate":
        check = [sys.executable, str(ROOT / "scripts/zones.py"), "verify"]
        return subprocess.run(check, cwd=ROOT, check=False, capture_output=True).returncode == 0
    raise ValueError(f"no way to check gate {name!r}")


def plan(gate: GatePolicy, platforms: list[str]) -> list[str]:
    """The gate's needs for HEAD, each with what proves it or the command that would."""
    policy = load_policy()
    _, tree, _ = assurance_gate.clean_head()
    here = platform()
    lines = [f"{gate.name} for tree {tree[:12]} (this machine: {here or 'no Docker'})"]
    lines += [
        f"  {'ok  ' if gate_holds(required, tree) else 'need'}  {required:<22} {'':<14} just {required}"
        for required in gate.gates
    ]
    for need in needs(gate, platforms):
        recipe = policy.tiers[need.tier].recipe
        receipt = current(need, tree)
        where = need.platform if need.platform != "any" else "any platform"
        if receipt is not None:
            lines.append(f"  ok    {need.tier:<22} {where:<14} {receipt.run} on {receipt.machine}")
            continue
        last = latest(need)
        stale = f"; last proven on {last.revision[:10] if last.revision else '?'}" if last else ""
        command = (
            f"just {recipe}" if need.platform in {"any", here} else f"just on <a {need.platform} machine> {recipe}"
        )
        lines.append(f"  need  {need.tier:<22} {where:<14} {command}{stale}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    certifying = commands.add_parser("certify")
    certifying.add_argument("--tier", required=True)
    certifying.add_argument("--run", type=Path)
    certifying.add_argument("--invocation", default=os.environ.get("REPO2REE_TEST_RUN_ID"))
    certifying.add_argument("--if-eligible", action="store_true")
    for name in ("missing", "require", "plan"):
        command = commands.add_parser(name)
        command.add_argument("gate")
        command.add_argument("--platforms", default="", help="the platforms an `each` tier must pass on")
    args = parser.parse_args()

    if args.command == "certify":
        policy = load_policy()
        if args.tier not in policy.tiers:
            raise SystemExit(f"no tier {args.tier!r} in {POLICY}")
        found = runs_of(args.tier, args.invocation, args.run)
        try:
            if not found:
                raise ReceiptError(f"no {args.tier} run of this invocation to certify")
            receipt = certify(policy.tiers[args.tier], found[0])
        except ReceiptError as error:
            print(f">> {error}", file=sys.stderr)
            return 0 if args.if_eligible else 1
        print(f">> {args.tier} receipt for {receipt.tree[:12]} on {receipt.platform} ({receipt.tests} tests)")
        return 0

    gate = gate_policy(args.gate)
    platforms = args.platforms.split()
    if args.command == "plan":
        print("\n".join(plan(gate, platforms)))
        return 0
    _, tree, _ = assurance_gate.clean_head()
    if args.command == "missing":
        here = platform()
        policy = load_policy()
        for need in unmet(gate, platforms, tree):
            if need.platform in {"any", here}:
                print(need.tier, policy.tiers[need.tier].recipe)
        return 0
    if gaps := unmet(gate, platforms, tree):
        print(f">> {gate.name} lacks a current receipt for:", file=sys.stderr)
        for need in gaps:
            print(f"   {need.tier} on {need.platform}", file=sys.stderr)
        print(">> see: just gate-plan " + gate.name, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
