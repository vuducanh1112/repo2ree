"""The published contract: the generated schema and the checker agree on every record."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from repo2ree_conformance.cli import main
from repo2ree_conformance.contract import record_problems
from repo2ree_conformance.files import GENERATED_SCHEMA, load_spec

SPEC = load_spec()
SCHEMA = json.loads(GENERATED_SCHEMA.read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
SAMPLE = {"str": "x", "str?": "x", "bool": True, "bool?": False, "int": 1, "int?": 1}
WRONG = {"str": 1, "str?": 1, "bool": "yes", "bool?": 0, "int": True, "int?": "1"}


def envelope(seq: int = 2, **fields: Any) -> dict[str, Any]:
    return {"v": 1, "seq": seq, "at": "2026-10-21T00:00:00+00:00"} | fields


def header(process: str = "api", **changes: Any) -> dict[str, Any]:
    fields = {
        "kind": "journal.opened",
        "process": process,
        "epoch": 1,
        "hosts": sorted(SPEC.hosted_by(process)),
        "vocabulary": SPEC.vocabulary_digest,
        "pid": 7,
    }
    return envelope(1, **(fields | changes))


def transitions() -> Iterator[dict[str, Any]]:
    """One record per entity and target state, carrying every declared fact."""
    for name, entity in sorted(SPEC.entities.items()):
        facts = {fact: entity.allowed.get(fact, (SAMPLE[kind],))[0] for fact, kind in entity.facts.items()}
        for target in entity.states:
            yield envelope(
                kind="transition",
                owner=entity.owner,
                subject=name,
                key="k1",
                partition="ree-1",
                to=target,
                facts=facts,
            ) | {"from": None}


def messages() -> Iterator[dict[str, Any]]:
    for name, boundary in sorted(SPEC.boundaries.items()):
        for kind, message in [("send", boundary.request), *(("receive", item) for item in boundary.responses)]:
            facts = {fact: SAMPLE[type_] for fact, type_ in boundary.facts.get(message, {}).items()}
            yield envelope(
                kind=kind,
                owner=boundary.sender,
                subject=name,
                key="k1",
                partition="ree-1",
                message=message,
                facts=facts,
            )
        yield envelope(
            kind="abandon",
            owner=boundary.sender,
            subject=name,
            key="k1",
            partition="ree-1",
            message=None,
            facts={"reason": "timeout"},
        )


def mutations(record: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Ways to break (or legitimately extend) one record; each is judged by both readers."""

    def changed(label: str, change: Any) -> tuple[str, dict[str, Any]]:
        copied = copy.deepcopy(record)
        change(copied)
        return label, copied

    yield changed("an extra fact", lambda r: r.setdefault("facts", {}).update(owner_note="kept"))
    yield changed("another owner", lambda r: r.update(owner="someone"))
    yield changed("a numeric key", lambda r: r.update(key=7))
    yield changed("no key", lambda r: r.pop("key"))
    yield changed("a list of facts", lambda r: r.update(facts=[]))
    yield changed("a numeric partition", lambda r: r.update(partition=3))
    yield changed("no sequence number", lambda r: r.pop("seq"))
    yield changed("version 2", lambda r: r.update(v=2))
    subject = record["subject"]
    if subject in SPEC.entities:
        entity = SPEC.entities[subject]
        yield changed("an unknown target", lambda r: r.update(to="elsewhere"))
        yield changed("an unknown source", lambda r: r.update({"from": "elsewhere"}))
        yield changed("a message kind", lambda r: r.update(kind="send", message="x"))
        for fact, kind in entity.facts.items():
            yield changed(f"{fact} of another type", lambda r, f=fact, k=kind: r["facts"].update({f: WRONG[k]}))
            yield changed(f"{fact} null", lambda r, f=fact: r["facts"].update({f: None}))
            yield changed(f"{fact} absent", lambda r, f=fact: r["facts"].pop(f))
            if fact in entity.allowed:
                yield changed(f"{fact} unlisted", lambda r, f=fact: r["facts"].update({f: "unlisted"}))
    elif record["kind"] == "abandon":
        yield changed("an abandonment with a message", lambda r: r.update(message="result"))
        yield changed("a numeric reason", lambda r: r["facts"].update(reason=1))
    else:
        boundary = SPEC.boundaries[subject]
        yield changed("a transition", lambda r: r.update(kind="transition", to="sent"))
        yield changed("another message", lambda r: r.update(message="elsewhere"))
        for fact, kind in boundary.facts.get(record["message"], {}).items():
            yield changed(f"{fact} of another type", lambda r, f=fact, k=kind: r["facts"].update({f: WRONG[k]}))
            yield changed(f"{fact} absent", lambda r, f=fact: r["facts"].pop(f))


def corpus() -> Iterator[tuple[str, dict[str, Any]]]:
    yield "a header", header()
    yield "a header without a vocabulary", {k: v for k, v in header().items() if k != "vocabulary"}
    yield "a header speaking for other components", header(hosts=["api"])
    yield "a close", envelope(9, kind="journal.closed")
    yield "a final close", envelope(9, kind="journal.closed", final=True)
    yield "a close that is not final", envelope(9, kind="journal.closed", final=False)
    yield "an unknown kind", envelope(kind="journal.rotated")
    own = envelope(kind="transition", owner="api", subject="Deposit", key="d1", to="started", facts={"any": [1]})
    yield "an undeclared subject", own
    yield "an undeclared subject without a key", {k: v for k, v in own.items() if k != "key"}
    for record in [*transitions(), *messages()]:
        label = f"{record['subject']} {record.get('to') or record.get('message') or record['kind']}"
        yield label, record
        for change, mutated in mutations(record):
            yield f"{label} with {change}", mutated


CORPUS = list(corpus())


def test_the_schema_is_a_valid_json_schema_naming_its_vocabulary() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["x-vocabulary"] == SPEC.vocabulary_digest


@pytest.mark.parametrize(("label", "record"), CORPUS, ids=[label for label, _ in CORPUS])
def test_the_schema_and_the_checker_agree_on_every_record(label: str, record: dict[str, Any]) -> None:
    problems = record_problems(SPEC, record)
    schema_errors = [error.message for error in VALIDATOR.iter_errors(record)]
    assert (not problems) == (not schema_errors), f"checker: {problems}; schema: {schema_errors[:3]}"


def test_the_corpus_holds_both_kept_and_broken_records() -> None:
    kept = sum(1 for _, record in CORPUS if not record_problems(SPEC, record))
    assert 20 < kept < len(CORPUS) - 100


def test_required_facts_are_missing_only_where_the_vocabulary_requires_them() -> None:
    queued = next(r for r in transitions() if r["subject"] == "Run" and r["to"] == "queued")
    running = next(r for r in transitions() if r["subject"] == "Run" and r["to"] == "running")
    queued["facts"].pop("operation")
    running["facts"].pop("operation")
    assert record_problems(SPEC, queued) == ["missing required facts ['operation']"]
    assert record_problems(SPEC, running) == []


def write_journal(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


def test_validate_journal_accepts_a_journal_that_keeps_the_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = next(r for r in transitions() if r["subject"] == "Run" and r["to"] == "queued")
    write_journal(tmp_path / "api-000001.ndjson", [header(), run, envelope(3, kind="journal.closed", final=True)])
    assert main(["validate-journal", str(tmp_path)]) == 0
    assert capsys.readouterr().out.startswith("ok: ")


def test_validate_journal_lists_what_breaks_the_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run = next(r for r in transitions() if r["subject"] == "Run" and r["to"] == "queued")
    run["facts"] = {}
    path = write_journal(
        tmp_path / "api-000001.ndjson",
        [header(), envelope(3) | {k: v for k, v in run.items() if k not in {"v", "seq", "at"}}],
    )
    assert main(["validate-journal", str(path)]) == 1
    out = capsys.readouterr().out
    assert "sequence jumps from 1 to 3" in out
    assert "seq 3: missing required facts ['operation']" in out


def test_validate_journal_refuses_to_pass_without_journals(tmp_path: Path) -> None:
    assert main(["validate-journal", str(tmp_path)]) == 1
