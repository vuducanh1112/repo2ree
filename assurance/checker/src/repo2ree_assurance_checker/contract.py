"""Whether journal records keep the published contract, judged record by record.

This is the checker's own reading of ``contracts/behaviour/events.schema.json``: the
schema is generated from the same vocabulary, and a test holds the two to the same
answer on every record. ``validate-journal`` applies it to journal files, so an owner
in any language can test what it writes before a gated run judges it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from repo2ree_assurance_checker.sources import read_journal
from repo2ree_assurance_checker.spec import Spec, fact_problems

RECORD_KINDS = ("transition", "send", "receive", "abandon")


def _optional_string(record: dict[str, Any], field: str) -> bool:
    return field not in record or record[field] is None or isinstance(record[field], str)


def header_problems(spec: Spec, record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    process, hosts = record.get("process"), record.get("hosts")
    if not isinstance(process, str):
        problems.append("journal.opened names no process")
    if not isinstance(record.get("epoch"), int) or isinstance(record.get("epoch"), bool) or record["epoch"] < 1:
        problems.append("journal.opened has no epoch")
    if not isinstance(hosts, list) or not all(isinstance(host, str) for host in hosts):
        problems.append("journal.opened lists no hosts")
    elif isinstance(process, str) and (expected := sorted(spec.hosted_by(process))) and hosts != expected:
        problems.append(f"journal.opened speaks for {hosts}, the vocabulary places {expected} in {process}")
    if not isinstance(record.get("vocabulary"), str):
        problems.append("journal.opened names no vocabulary")
    return problems


def record_problems(spec: Spec, record: object) -> list[str]:
    """Why one journal line breaks the contract; empty when it keeps it."""
    if not isinstance(record, dict):
        return ["not an object"]
    problems: list[str] = []
    if record.get("v") != 1:
        problems.append("v is not 1")
    if not isinstance(record.get("seq"), int) or isinstance(record.get("seq"), bool) or record["seq"] < 1:
        problems.append("no sequence number")
    kind = record.get("kind")
    if kind == "journal.opened":
        return problems + header_problems(spec, record)
    if kind == "journal.closed":
        return problems + ([] if record.get("final", True) is True else ["final is not true"])
    if kind not in RECORD_KINDS:
        return [*problems, f"unknown kind {kind!r}"]
    if not all(isinstance(record.get(field), str) for field in ("subject", "owner", "key")):
        return [*problems, "subject, owner, and key must be strings"]
    facts = record.get("facts", {})
    if not isinstance(facts, dict):
        return [*problems, "facts is not an object"]
    if not _optional_string(record, "partition"):
        problems.append("partition is not a string")
    subject = record["subject"]
    if subject in spec.entities:
        return problems + _transition_problems(spec, record, facts)
    if subject in spec.boundaries:
        return problems + _message_problems(spec, record, facts)
    return problems  # The owner's own subject: never judged.


def _transition_problems(spec: Spec, record: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    entity = spec.entities[record["subject"]]
    problems: list[str] = []
    if record["kind"] != "transition":
        problems.append(f"{entity.name} is an entity: its records are transitions")
    if record["owner"] != entity.owner:
        problems.append(f"recorded by {record['owner']}, but {entity.owner} owns {entity.name}")
    source, target = record.get("from"), record.get("to")
    if source is not None and source not in entity.states:
        problems.append(f"from {source!r} is not a state of {entity.name}")
    if target not in entity.states:
        problems.append(f"to {target!r} is not a state of {entity.name}")
    required = entity.required.get(target, ()) if isinstance(target, str) else ()
    return problems + [problem for _, problem in fact_problems(entity.facts, required, facts, entity.allowed)]


def _message_problems(spec: Spec, record: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    boundary = spec.boundaries[record["subject"]]
    kind, message = record["kind"], record.get("message")
    problems: list[str] = []
    if record["owner"] != boundary.sender:
        problems.append(f"recorded by {record['owner']}, but {boundary.sender} sends {boundary.name}")
    if kind == "transition":
        return [*problems, f"{boundary.name} is a boundary: its records are messages"]
    if kind == "abandon":
        if message is not None:
            problems.append("an abandonment carries no message")
        if not _optional_string(facts, "reason"):
            problems.append("reason is not a string")
        return problems
    allowed = [boundary.request] if kind == "send" else list(boundary.responses)
    if message not in allowed:
        return [*problems, f"{kind} {message!r} is not one of {allowed}"]
    declared, required = boundary.facts.get(message, {}), boundary.required.get(message, ())
    values = boundary.allowed.get(message, {})
    return problems + [problem for _, problem in fact_problems(declared, required, facts, values)]


def journal_problems(spec: Spec, path: Path) -> list[str]:
    """Everything in one journal file that breaks the contract: its sequence, header, and records."""
    try:
        source, _ = read_journal(path)
    except ValueError as exc:
        return [str(exc)]
    problems = list(source.problems)
    for number, line in enumerate(path.read_bytes().splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue  # read_journal already reported it.
        seq = record.get("seq") if isinstance(record, dict) else None
        where = f"seq {seq}" if isinstance(seq, int) else f"line {number}"
        problems += [f"{where}: {problem}" for problem in record_problems(spec, record)]
    return problems
