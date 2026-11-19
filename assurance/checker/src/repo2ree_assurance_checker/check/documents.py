"""Each commit of a document judged alone: its receipts' standings, and the digests it records.

The checker reads the committed document and the files the commit holds, and computes every digest
itself, in the encodings the format's fixtures pin (``contracts/ree/fixtures``). A receipt's standing
is what its basis gives; what core recorded of it is compared with that, never taken from it.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterator, Mapping

from pydantic import JsonValue

from repo2ree_assurance_checker.check.aggregates import experiment_slug
from repo2ree_assurance_checker.check.reading import TOKEN, Judged, held, items, value, values, within
from repo2ree_assurance_checker.check.results import Finding, RuleResult
from repo2ree_assurance_checker.check.reviews import agreements, references, reviewed, verdicts
from repo2ree_assurance_checker.check.signatures import UnreadableBundleError, signed_statement
from repo2ree_assurance_checker.evidence import CommittedFile, Event, Evidence, Snapshot
from repo2ree_assurance_checker.spec import (
    ITEM,
    KEYED,
    AggregateSpec,
    AgreesPair,
    BasisPair,
    CanonicalPair,
    DocumentRule,
    FilePair,
    PathsPair,
    ReceiptMachine,
    ReferencePair,
    Spec,
)
from repo2ree_assurance_checker.spec.documents import SIGNATURE_SUFFIX

# How a commit's cause reads as a receipt's: the first commit is the receipts' baseline.
_RECEIPT_CAUSE = {"created": "baseline", "operation": "operation", "external": "external"}
_EXACT = 2**53


# ================================================
# The checker's own digests
# ================================================


def _fold(entries: list[tuple[str, str]]) -> str:
    hasher = hashlib.sha256()
    for path, digest in entries:
        hasher.update(path.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\0")
    return f"sha256:{hasher.hexdigest()}"


def _by_parts(path: str) -> tuple[str, ...]:
    return tuple(path.split("/"))


def paths_digest(files: Mapping[str, CommittedFile], root: str, paths: list[str]) -> str | None:
    """The declared paths under ``root``, each a file or every file below it; None when none is declared."""
    if not paths:
        return None
    entries: list[tuple[str, str]] = []
    for declared in sorted(set(paths)):
        full = root + declared
        if full in files:
            entries.append((declared, files[full].digest))
            continue
        below = sorted((path for path in files if path.startswith(f"{full}/")), key=_by_parts)
        entries.extend((f"{declared}/{path.removeprefix(full + '/')}", files[path].digest) for path in below)
    return _fold(entries)


def canonical(value: JsonValue) -> str:
    """The canonical encoding: members sorted by their UTF-16 code units, no insignificant space, no
    floating-point numbers."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        if not -_EXACT < value < _EXACT:
            raise ValueError(f"integer {value} has no exact canonical encoding")
        return str(value)
    if isinstance(value, float):
        raise ValueError(f"a canonical document holds no floating-point number: {value!r}")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(canonical(item) for item in value) + "]"
    members = sorted(value.items(), key=lambda member: member[0].encode("utf-16-be"))
    return "{" + ",".join(f"{json.dumps(key, ensure_ascii=False)}:{canonical(inner)}" for key, inner in members) + "}"


def canonical_digest(domain: str, name: str, value: JsonValue) -> str:
    return f"sha256:{hashlib.sha256(canonical({'domain': domain, name: value}).encode('utf-8')).hexdigest()}"


# ================================================
# Receipts' standings
# ================================================


def _agrees(pair: BasisPair, receipt: JsonValue, document: Mapping[str, JsonValue], item: str | None) -> bool:
    return within(receipt, pair.recorded) == value(document, pair.now, item)


def _standing(
    receipt: ReceiptMachine,
    recorded: JsonValue,
    applicable: bool,
    document: Mapping[str, JsonValue],
    item: str | None,
) -> str:
    if recorded is None:
        return "missing" if applicable else "not_applicable"
    if not applicable:
        return "stale"
    agreeing = all(_agrees(pair, recorded, document, item) for pair in receipt.basis or ())
    return "current" if agreeing else "stale"


def standings(aggregate: AggregateSpec, snapshot: Snapshot) -> dict[str, str]:
    """Each receipt's standing in one commit, by its step: ``<receipt>`` or ``<receipt>:<item>``."""
    document = snapshot.document or {}
    found: dict[str, str] = {}
    for name, receipt in aggregate.receipts.items():
        at = aggregate.location(name)
        if receipt.keyed:
            about = next(path for path in receipt.about if path.endswith(KEYED))
            declared = {item for item, part in values(document, about) if item is not None and held(part)}
            recorded = dict(items(value(document, at)))
            for item in sorted(declared | {item for item, part in recorded.items() if part is not None}):
                found[f"{name}:{item}"] = _standing(receipt, recorded.get(item), item in declared, document, item)
            continue
        recorded_receipt = value(document, at)
        applicable = all(held(value(document, path)) for path in receipt.about)
        if receipt.applies_without_declaration:
            applicable = applicable or recorded_receipt is not None
        found[name] = _standing(receipt, recorded_receipt, applicable, document, None)
    return found


def _ordered(evidence: Evidence, snapshots: list[Snapshot]) -> list[Snapshot]:
    ranks = {source.id: (*source.lineage, source.rank) for source in evidence.sources}
    return sorted(snapshots, key=lambda snapshot: (*ranks.get(snapshot.source, ("", "", 0)), snapshot.position))


def _witnessed(spec: Spec) -> dict[str, AggregateSpec]:
    """The aggregates whose receipts all stand on a basis, by the entity whose document they are."""
    return {
        name: aggregate
        for name, aggregate in spec.aggregates.items()
        if aggregate.receipts and all(receipt.basis is not None for receipt in aggregate.receipts.values())
    }


def receipt_events(spec: Spec, evidence: Evidence) -> Iterator[Event]:
    """Each receipt's standing as it changes, commit by commit, as its basis gives it."""
    aggregates = _witnessed(spec)
    by_instance: dict[tuple[str, str, str], list[Snapshot]] = defaultdict(list)
    for snapshot in evidence.snapshots:
        if snapshot.subject in aggregates and snapshot.document is not None:
            by_instance[(snapshot.subject, snapshot.source, snapshot.partition)].append(snapshot)
    for (subject, _, partition), found in sorted(by_instance.items()):
        aggregate = aggregates[subject]
        states: dict[str, str] = {}
        for snapshot in _ordered(evidence, found):
            now = standings(aggregate, snapshot)
            for offset, step in enumerate(sorted(now.keys() | states.keys())):
                target = now.get(step, "not_applicable")
                if states.get(step) == target:
                    continue
                yield Event(
                    source=snapshot.source,
                    position=snapshot.position + offset,
                    kind="transition",
                    owner=spec.entities[aggregate.receipt_entity].owner,
                    subject=aggregate.receipt_entity,
                    key=f"{partition}/{step}",
                    partition=partition,
                    source_state=states.get(step),
                    target_state=target,
                    facts={
                        "step": step,
                        "kind": step.partition(":")[0],
                        "operation": snapshot.operation,
                        "attempt_id": snapshot.attempt_id,
                        "cause": _RECEIPT_CAUSE[snapshot.cause],
                    },
                    locator=snapshot.locator,
                )
                states[step] = target


def witness(spec: Spec, evidence: Evidence) -> Evidence:
    """The evidence with its receipts' standings among its events, as the checker reads them; once."""
    if evidence.witnessed:
        return evidence
    found = tuple(receipt_events(spec, evidence))
    return evidence.model_copy(update={"events": (*evidence.events, *found), "witnessed": True})


# ================================================
# Document rules
# ================================================


def _items_of(document: Mapping[str, JsonValue], path: str) -> list[str | None]:
    if KEYED not in path:
        return [None]
    return [item for item, _ in values(document, path)]


def _bound(path: str) -> str:
    return path.replace(KEYED, ITEM)


def _slugged(path: str, item: str | None) -> str:
    return path.replace("{slug}", experiment_slug(item)) if item is not None else path


def _file_pairs(rule: DocumentRule, pair: FilePair, snapshot: Snapshot) -> Iterator[Judged]:
    document = snapshot.document or {}
    for item in _items_of(document, pair.digest):
        recorded = value(document, _bound(pair.digest), item)
        if recorded is None:
            continue
        named = value(document, _bound(pair.file), item) if pair.file else pair.path
        subject = f"{_bound(pair.digest).replace(ITEM, f'[{item}]')}"
        if not isinstance(named, str) or not named:
            yield Judged(subject, False, "records a digest, but names no file")
            continue
        path = _slugged(pair.root, item) + _slugged(named, item)
        committed = snapshot.files.get(path)
        if committed is None:
            if rule.absent == "violated":
                yield Judged(subject, False, f"records the digest of {path}, which the commit does not hold")
            else:
                yield Judged(subject, None)
            continue
        if committed.digest != recorded:
            yield Judged(subject, False, f"records {recorded}, but {path} is {committed.digest}")
            continue
        size = value(document, _bound(pair.size), item) if pair.size else None
        if size is not None and size != committed.size:
            yield Judged(subject, False, f"records a size of {size}, but {path} holds {committed.size} bytes")
            continue
        yield Judged(subject, True)


def _paths_pairs(rule: DocumentRule, pair: PathsPair, snapshot: Snapshot) -> Iterator[Judged]:
    document = snapshot.document or {}
    for item in _items_of(document, pair.digest):
        recorded = value(document, _bound(pair.digest), item)
        if recorded is None:
            continue
        subject = _bound(pair.digest).replace(ITEM, f"[{item}]")
        root = _slugged(pair.root, item)
        if not any(path.startswith(root) for path in snapshot.files):
            yield Judged(
                subject, None if rule.absent == "unevidenced" else False, f"the commit holds nothing under {root}"
            )
            continue
        declared = value(document, _bound(pair.paths), item)
        paths = [path for path in declared if isinstance(path, str)] if isinstance(declared, list) else []
        computed = paths_digest(snapshot.files, root, paths)
        if computed != recorded:
            yield Judged(subject, False, f"records {recorded}, but the outputs under {root} are {computed}")
            continue
        yield Judged(subject, True)


def _canonical_pairs(pair: CanonicalPair, snapshot: Snapshot) -> Iterator[Judged]:
    document = snapshot.document or {}
    recorded = value(document, pair.digest)
    if recorded is None:
        return
    name = TOKEN.findall(pair.part)[-1]
    try:
        computed = canonical_digest(pair.domain, name, value(document, pair.part))
    except ValueError as exc:
        yield Judged(pair.digest, False, f"{pair.part} has no canonical encoding: {exc}")
        return
    if computed != recorded:
        yield Judged(pair.digest, False, f"records {recorded}, but {pair.part} is {computed}")
        return
    yield Judged(pair.digest, True)


def _inventory(rule: DocumentRule, snapshot: Snapshot) -> Iterator[Judged]:
    document = snapshot.document or {}
    listed = value(document, rule.inventory or "")
    entries: dict[str, dict[str, JsonValue]] = {
        path: entry
        for entry in (listed if isinstance(listed, list) else [])
        if isinstance(entry, dict) and isinstance(path := entry.get("path"), str)
    }
    carried = {path: file for path, file in snapshot.files.items() if not rule.excepts(path)}
    for path in sorted(entries.keys() | carried.keys()):
        entry, committed = entries.get(path), carried.get(path)
        if entry is None:
            yield Judged(path, False, "is held by the commit, but the inventory does not list it")
        elif committed is None:
            yield Judged(path, False, "is listed by the inventory, but the commit does not hold it")
        elif entry.get("digest") != committed.digest or entry.get("size") != committed.size:
            yield Judged(
                path,
                False,
                f"is listed as {entry.get('digest')} of {entry.get('size')} bytes, "
                f"but holds {committed.digest} of {committed.size}",
            )
        else:
            yield Judged(path, True)


def _signatures(rule: DocumentRule, snapshot: Snapshot, *, review: bool = False) -> Iterator[Judged]:
    """Each signature the commit carries; a review's statement carries the review's record as its predicate."""
    document = snapshot.document or {}
    directory = rule.files or ""
    signed = value(document, rule.subject or "", whole=review)
    for path, committed in sorted(snapshot.files.items()):
        if not path.startswith(directory):
            continue
        name = path.removeprefix(directory)
        claim = name.removesuffix(SIGNATURE_SUFFIX) if name.endswith(SIGNATURE_SUFFIX) else None
        if claim not in rule.claims:
            named = ", ".join(f"{claim}{SIGNATURE_SUFFIX}" for claim in sorted(rule.claims))
            yield Judged(path, False, f"is no claim's signature: a signature is one of {named}")
            continue
        if committed.content is None:
            yield Judged(path, False, "is an LFS payload, but a signature is committed to git")
            continue
        try:
            statement = signed_statement(committed.content)
        except UnreadableBundleError as exc:
            yield Judged(path, False, str(exc))
            continue
        if signed not in statement.digests:
            yield Judged(path, False, f"signs {', '.join(sorted(statement.digests))}, not {rule.subject} {signed}")
        elif statement.predicate_type != rule.claims[claim]:
            yield Judged(path, False, f"claims {statement.predicate_type}, but its name says {rule.claims[claim]}")
        elif review and statement.predicate != document:
            yield Judged(path, False, "signs another record than the review holds in this commit")
        else:
            yield Judged(path, True)


def _standings_recorded(aggregate: AggregateSpec, snapshot: Snapshot) -> Iterator[Judged]:
    if snapshot.recorded is None:
        return
    given = standings(aggregate, snapshot)
    for step in sorted(given.keys() | snapshot.recorded.keys()):
        recorded, own = snapshot.recorded.get(step), given.get(step)
        if recorded is None:
            yield Judged(step, False, f"core recorded no standing; its basis gives {own}")
        elif own is None:
            yield Judged(step, False, f"core recorded {recorded} for a receipt the specification does not know")
        elif recorded != own:
            yield Judged(step, False, f"core recorded {recorded}, but its basis gives {own}")
        else:
            yield Judged(step, True)


def _review(rule: DocumentRule, snapshot: Snapshot, reviewed: Mapping[str, JsonValue] | None) -> Iterator[Judged]:
    document = snapshot.document or {}
    if rule.pattern == "signature":
        yield from _signatures(rule, snapshot, review=True)
    elif rule.pattern == "verdict":
        yield from verdicts(rule, document)
    else:
        for pair in rule.pairs:
            if isinstance(pair, ReferencePair):
                yield from references(pair, document, reviewed)
            elif isinstance(pair, AgreesPair):
                yield from agreements(pair, document)


def judged(rule: DocumentRule, aggregate: AggregateSpec, snapshot: Snapshot) -> Iterator[Judged]:
    if snapshot.document is None:
        return
    if rule.sealed is not None and (snapshot.document.get("seal") is not None) != rule.sealed:
        return
    if rule.pattern == "standing":
        yield from _standings_recorded(aggregate, snapshot)
    elif rule.pattern == "signature":
        yield from _signatures(rule, snapshot)
    elif rule.kind == "inventory":
        yield from _inventory(rule, snapshot)
    else:
        for pair in rule.pairs:
            if isinstance(pair, FilePair):
                yield from _file_pairs(rule, pair, snapshot)
            elif isinstance(pair, PathsPair):
                yield from _paths_pairs(rule, pair, snapshot)
            elif isinstance(pair, CanonicalPair):
                yield from _canonical_pairs(pair, snapshot)


def check_documents(spec: Spec, evidence: Evidence) -> list[RuleResult]:
    """Every document rule over every commit of its document: an aggregate's, or a review's beside the REE it
    reviews."""
    results: list[RuleResult] = []
    for name, rules in spec.documents.items():
        aggregate = spec.aggregates[rules.aggregate]
        snapshots = [snapshot for snapshot in evidence.snapshots if snapshot.subject == name]
        beside = _ordered(
            evidence, [snapshot for snapshot in evidence.snapshots if snapshot.subject == rules.aggregate]
        )
        for rule in rules.rules:
            triggered = 0
            findings: list[Finding] = []
            for snapshot in _ordered(evidence, snapshots):
                judgements = (
                    _review(rule, snapshot, reviewed(rules, snapshot, beside))
                    if rules.reviews is not None
                    else judged(rule, aggregate, snapshot)
                )
                for judgement in judgements:
                    if judgement.held is None:
                        continue
                    triggered += 1
                    if not judgement.held:
                        findings.append(
                            Finding(
                                verdict="violated",
                                subject=f"{name} {snapshot.partition} {judgement.subject}",
                                reason=judgement.reason,
                                evidence=(snapshot.ref,),
                            )
                        )
            results.append(
                RuleResult(
                    rule=f"document:{rule.id}",
                    kind="document",
                    summary=rule.summary,
                    triggered=triggered,
                    findings=tuple(findings),
                )
            )
    return results
