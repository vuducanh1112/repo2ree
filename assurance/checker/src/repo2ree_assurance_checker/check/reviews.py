from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence

from pydantic import JsonValue

from repo2ree_assurance_checker.check.reading import TOKEN, Judged, value, values
from repo2ree_assurance_checker.evidence import Snapshot
from repo2ree_assurance_checker.spec import AgreesPair, DocumentRule, DocumentRules, ReferencePair, VerdictPolicy

type Document = Mapping[str, JsonValue]


def reviewed(rules: DocumentRules, snapshot: Snapshot, ree: Sequence[Snapshot]) -> Document | None:
    seal = value(snapshot.document or {}, rules.reviews or "", whole=True)
    if not isinstance(seal, str):
        return None
    for candidate in reversed(ree):
        document = candidate.document or {}
        if value(document, "seal.ree_digest") == seal:
            return document
    return None


def _recorded(document: Document, path: str) -> bool:
    return value(document, TOKEN.findall(path)[0], whole=True) is not None


def _paired(document: Document, path: str) -> Iterator[tuple[str | None, JsonValue]]:
    if not _recorded(document, path):
        return
    yield from values(document, path, whole=True)


def references(pair: ReferencePair, review: Document, ree: Document | None) -> Iterator[Judged]:
    for item, recorded in _paired(review, pair.field):
        subject = pair.field if item is None else f"{pair.field} {item}"
        if ree is None:
            yield Judged(subject, None)
            continue
        expected = value(ree, pair.ree, item)
        if recorded == expected:
            yield Judged(subject, True)
        else:
            yield Judged(subject, False, f"records {recorded!r}, but the reviewed REE's {pair.ree} is {expected!r}")


def agreements(pair: AgreesPair, review: Document) -> Iterator[Judged]:
    for item, recorded in _paired(review, pair.field):
        subject = pair.field if item is None else f"{pair.field} {item}"
        same = value(review, pair.same, item, whole=True)
        if recorded == same:
            yield Judged(subject, True)
        else:
            yield Judged(subject, False, f"records {recorded!r}, but its {pair.same} is {same!r}")


def _swhid(comparison: Document) -> str:
    expected, observed = comparison.get("expected_swhid"), comparison.get("observed_swhid")
    if not expected or not observed:
        return "inconclusive"
    return "identical" if expected == observed else "different"


def _int(value: JsonValue) -> int:
    return value if isinstance(value, int) else 0


def _closure(comparison: Document) -> str:
    expected = comparison.get("expected_artifact_digest")
    if expected and expected == comparison.get("observed_artifact_digest"):
        return "identical"
    if not _int(comparison.get("expected_package_total")) or not _int(comparison.get("observed_package_total")):
        return "inconclusive"
    decisive = sum(_int(comparison.get(count)) for count in ("missing_count", "extra_count", "version_mismatch_count"))
    return "equivalent" if decisive == 0 else "different"


def _activation(outcome: Document) -> str:
    return "passed" if outcome.get("exit_code") == 0 else "failed"


def _verify(comparison: Document) -> str:
    criterion = comparison.get("expected_verify_script_digest")
    activation = comparison.get("expected_activate_experiment_environment_script_digest")
    if (
        comparison.get("expected_verify_exit_code") != 0
        or criterion is None
        or criterion != comparison.get("verify_script_digest")
        or activation is None
        or activation != comparison.get("activate_experiment_environment_script_digest")
    ):
        return "inconclusive"
    if comparison.get("observed_verify_exit_code") != 0:
        return "different"
    expected = comparison.get("expected_output_digest")
    return (
        "identical" if expected is not None and expected == comparison.get("observed_output_digest") else "reproduced"
    )


def _settled(subject: str, part: JsonValue, ladder: str) -> Judged:
    recorded = part.get("verdict") if isinstance(part, dict) else None
    if recorded == ladder:
        return Judged(subject, True)
    return Judged(subject, False, f"records {recorded!r}, but its ladder gives {ladder!r}")


def _counts(subject: str, comparison: Document) -> Iterator[Judged]:
    for listed, count in (
        ("missing", "missing_count"),
        ("extra", "extra_count"),
        ("version_mismatches", "version_mismatch_count"),
        ("advisory", "advisory_count"),
    ):
        found = comparison.get(listed)
        length = len(found) if isinstance(found, list) else 0
        counted = comparison.get(count, 0)
        if counted != length:
            yield Judged(f"{subject} {count}", False, f"counts {counted!r}, but lists {length}")
        else:
            yield Judged(f"{subject} {count}", True)


def _ladder(policy: VerdictPolicy, review: Document) -> Iterator[Judged]:
    if policy == "swhid" and isinstance(source := review.get("source_comparison"), dict):
        yield _settled("source_comparison", source, _swhid(source))
    elif policy == "sbom-closure" and isinstance(built := review.get("experiment_environment_comparison"), dict):
        yield _settled("experiment_environment_comparison", built, _closure(built))
        yield from _counts("experiment_environment_comparison", built)
    elif policy == "activation" and isinstance(activated := review.get("activation_outcome"), dict):
        yield _settled("activation_outcome", activated, _activation(activated))
    elif policy == "verify-script":
        for item, comparison in values(review, "experiment_comparisons[*]", whole=True):
            if isinstance(comparison, dict):
                yield _settled(f"experiment_comparisons {item}", comparison, _verify(comparison))
    elif policy == "after-activation" and (compared := review.get("experiment_comparisons")):
        activation = review.get("activation_outcome")
        passed = isinstance(activation, dict) and activation.get("verdict") == "passed"
        count = len(compared) if isinstance(compared, list) else 0
        yield Judged(
            "experiment_comparisons",
            passed,
            "" if passed else f"compares {count} experiments beside an activation that did not pass",
        )


def verdicts(rule: DocumentRule, review: Document) -> Iterator[Judged]:
    for policy in rule.policies:
        yield from _ladder(policy, review)
