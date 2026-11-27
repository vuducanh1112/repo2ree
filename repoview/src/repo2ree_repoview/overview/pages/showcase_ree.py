from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from repo2ree_repoview.overview.bundle import source_name
from repo2ree_repoview.overview.drawing import decision_svg
from repo2ree_repoview.overview.exports import Showcase, ShowcaseTest
from repo2ree_repoview.overview.html import Page, esc, section, table
from repo2ree_repoview.overview.showcase_ree import OVERLAY, Entry, Script, SealedRee, TargetResult, Written
from repo2ree_repoview.overview.showcase_review import Basis, FinalReview, PackageDelta, ReviewStatus, Verdict

WRITTEN: dict[Written, tuple[str, str]] = {
    "inferred": ("ok", "as inferred"),
    "chosen_over": ("ex", "chosen over inference"),
    "no_candidate": ("no", "inference proposed nothing"),
    "not_asked": ("no", "inference not asked"),
}
STATUS_TONE = {"complete": "ok", "needs_input": "ex", "not_inferred": "no"}
VERDICT_TONE: dict[Verdict, str] = {
    "identical": "ok",
    "equivalent": "ok",
    "reproduced": "ok",
    "passed": "ok",
    "inconclusive": "ex",
    "different": "no",
    "failed": "no",
}
REVIEW_TONE: dict[ReviewStatus, str] = {"completed": "ok", "running": "ex", "canceled": "ex", "failed": "no"}
BASIS: dict[Basis, str] = {
    "bundled": "against what the REE carries",
    "independent": "rebuilt from the recorded origin and recipe",
}


def slug(name: str) -> str:
    return f"showcase-ree-{name}"


def review_anchor(name: str) -> str:
    return f"showcase-review-{name}"


def _api_test(showcase: Showcase, workflow: str) -> ShowcaseTest | None:
    return next(
        (t for t in showcase.tests if t.surface == "api" and t.workflow == workflow and t.test is not None), None
    )


def _real_world_test(showcase: Showcase) -> ShowcaseTest | None:
    return next((t for t in showcase.tests if t.test is not None), None)


def authoring_test(showcase: Showcase) -> ShowcaseTest | None:
    return _real_world_test(showcase) if showcase.kind == "real_world" else _api_test(showcase, "authoring")


def review_test(showcase: Showcase) -> ShowcaseTest | None:
    return _real_world_test(showcase) if showcase.kind == "real_world" else _api_test(showcase, "review")


def _test_named(showcase: Showcase, workflow: str) -> str:
    return "test" if showcase.kind == "real_world" else f"API {workflow} test"


def badge(written: Written) -> str:
    tone, label = WRITTEN[written]
    return f'<span class="{tone}">{esc(label)}</span>'


def size(count: int) -> str:
    for unit, scale in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if count >= scale:
            return f"{count / scale:.1f} {unit}"
    return f"{count} B"


def code_block(text: str) -> str:
    return f'<pre class="code">{esc(text)}</pre>'


def answered(result: TargetResult | None) -> str:
    if result is None:
        return ""
    return (
        f'<span class="{STATUS_TONE[result.status]}">{esc(result.status)}</span>'
        f' <span class="muted">{esc(result.application)}</span>'
    )


def script_rows(ree: SealedRee) -> list[list[str]]:
    rows = []
    for script in ree.scripts:
        name = script.path.removeprefix(OVERLAY)
        rules = "<br>".join(dict.fromkeys(f"<code>{esc(p.candidate.inference_rule)}</code>" for p in script.proposals))
        rows.append(
            [
                f'<a href="#script-{esc(name)}"><code>{esc(name)}</code></a>',
                badge(script.written),
                answered(script.answer),
                rules,
            ]
        )
    return rows


def decision_block(script: Script) -> str:
    decision = script.decision
    if decision is None:
        return ""
    trace = decision.trace
    rows = [
        [
            f"<code>{esc(step.node_id)}</code>",
            esc(step.check or step.kind),
            esc(step.branch or step.outcome or ""),
            esc(step.observed.summary() if step.observed else ""),
        ]
        for step in trace.steps
    ]
    return (
        f"<details open><summary>How inference decided: <code>{esc(trace.dag)}</code> v{trace.version}, "
        f"ending at <code>{esc(trace.result_node)}</code></summary>"
        f'<div class="diagram full">{decision_svg(decision)}</div>'
        "<details><summary>the steps it took</summary>"
        + table(["Node", "Check", "Branch", "Observed"], rows)
        + "</details></details>"
    )


def script_section(script: Script) -> str:
    name = script.path.removeprefix(OVERLAY)
    parts = [f'<h4 id="script-{esc(name)}"><code>{esc(name)}</code> · {badge(script.written)}</h4>']
    proposal = script.proposal
    if proposal and script.written == "inferred":
        warnings = ", ".join(f"<code>{esc(w.code)}</code>" for w in proposal.candidate.warnings)
        parts.append(
            f'<p class="muted">The candidate of <code>{esc(proposal.candidate.inference_rule)}</code> '
            f"({esc(proposal.candidate.decision_leaf)}), written as proposed"
            + (f"; its warnings: {warnings}" if warnings else "")
            + ".</p>"
        )
    elif script.written == "chosen_over":
        rules = ", ".join(dict.fromkeys(f"<code>{esc(p.candidate.inference_rule)}</code>" for p in script.proposals))
        parts.append(f'<p class="muted">Inference proposed {rules}; the script written is none of them.</p>')
    elif script.written == "no_candidate":
        parts.append(
            f'<p class="muted">Inference was asked and answered {answered(script.answer)} with no candidate.</p>'
        )
    else:
        parts.append('<p class="muted">No inference request named this script before the seal.</p>')
    parts.append(decision_block(script))
    parts.append(code_block(script.body))
    return "".join(parts)


def request_rows(ree: SealedRee) -> list[list[str]]:
    rows = []
    for index, request in enumerate(ree.requests, 1):
        for result in request.results:
            candidates = "<br>".join(
                f'<code>{esc(c.inference_rule)}</code> <span class="muted">{esc(c.decision_leaf)}'
                + (f" · {esc(', '.join(w.code for w in c.warnings))}" if c.warnings else "")
                + "</span>"
                for c in result.candidates
            )
            rows.append(
                [
                    f'{index} <span class="muted"><code>{esc(request.commit[:10])}</code></span>',
                    f"<code>{esc(result.target.path)}</code>",
                    f'<span class="{STATUS_TONE[result.status]}">{esc(result.status)}</span>',
                    esc(result.application),
                    candidates or '<span class="muted">none</span>',
                ]
            )
    return rows


@dataclass
class _Folder:
    folders: dict[str, _Folder] = field(default_factory=dict)
    files: list[tuple[str, Entry]] = field(default_factory=list)

    def count(self) -> int:
        return len(self.files) + sum(folder.count() for folder in self.folders.values())


def _folder(entries: tuple[Entry, ...]) -> _Folder:
    root = _Folder()
    for entry in entries:
        *parents, name = entry.path.split("/")
        folder = root
        for parent in parents:
            folder = folder.folders.setdefault(parent, _Folder())
        folder.files.append((name, entry))
    return root


def file_leaf(name: str, entry: Entry) -> str:
    stored = '<span class="lfs">LFS</span>' if entry.lfs else "Git"
    meta = f'<span class="meta">{size(entry.lfs.size if entry.lfs else entry.size)} · {stored}</span>'
    if entry.text is None:
        return f"<li>{esc(name)}{meta}</li>"
    return f"<li><details><summary>{esc(name)}{meta}</summary>{code_block(entry.text)}</details></li>"


def folder_items(folder: _Folder) -> str:
    folders = "".join(
        f'<li><details open><summary><b>{esc(name)}/</b><span class="meta">{sub.count()} files</span></summary>'
        f"<ul>{folder_items(sub)}</ul></details></li>"
        for name, sub in sorted(folder.folders.items())
    )
    return folders + "".join(file_leaf(name, entry) for name, entry in sorted(folder.files, key=lambda f: f[0]))


def file_tree(entries: tuple[Entry, ...]) -> str:
    return f'<div class="filetree"><ul>{folder_items(_folder(entries))}</ul></div>'


def ree_body(ree: SealedRee, test: ShowcaseTest) -> str:
    written = Counter(script.written for script in ree.scripts)
    tally = " · ".join(f"{written[kind]} {badge(kind)}" for kind in WRITTEN if written[kind])
    sealed = ree.sealed
    cards = [
        ("Test", f"<code>{esc(test.test or '')}</code>"),
        ("Run", f"<code>{esc(test.run or '')}</code>"),
        ("REE", f"<code>{esc(ree.ree_id)}</code>"),
        ("Sealed", f"{esc(sealed.sealed_at)}<br><code>{esc(sealed.ree_digest)}</code>" if sealed else "—"),
        ("Scripts", tally or '<span class="muted">none</span>'),
    ]
    after = (
        f'<p class="muted">{ree.after_seal} operation(s) followed the seal; they are not shown.</p>'
        if ree.after_seal
        else ""
    )
    history = "".join(
        f"<li><code>{esc(op.operation)}</code> "
        f'<span class="{"ok" if op.outcome == "succeeded" else "no"}">{esc(op.outcome or "unrecorded")}</span> '
        f'<span class="muted"><code>{esc(op.commit[:10])}</code></span></li>'
        for op in ree.operations
    )
    return (
        '<div class="cards">'
        + "".join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in cards)
        + "</div>"
        + "<h3>Scripts</h3>"
        + table(["Script", "Written", "Inference answered", "Inference proposed"], script_rows(ree))
        + "".join(script_section(script) for script in ree.scripts)
        + "<h3>What inference was asked</h3>"
        + (
            table(["Request", "Target", "Status", "Application", "Candidates"], request_rows(ree))
            if ree.requests
            else '<p class="muted">Inference was not asked before the seal.</p>'
        )
        + "<h3>Files at the seal</h3>"
        + file_tree(ree.files)
        + "<h3>Operations to the seal</h3>"
        + f"<ol>{history}</ol>{after}"
        + f'<p class="muted">Read from <code>{esc(source_name(ree.source))}</code> at <code>{esc(ree.seal)}</code>.</p>'
    )


def verdict(value: Verdict) -> str:
    return f'<span class="{VERDICT_TONE[value]}">{esc(value)}</span>'


def basis(value: Basis) -> str:
    return f'{esc(value)}<br><span class="muted">{esc(BASIS[value])}</span>'


def digests(expected: str | None, observed: str | None) -> str:
    if expected == observed:
        return f'<code>{esc(observed or "—")}</code> <span class="muted">expected and observed</span>'
    return (
        f'<span class="muted">expected</span> <code>{esc(expected or "—")}</code><br>'
        f'<span class="muted">observed</span> <code>{esc(observed or "—")}</code>'
    )


def verdict_rows(review: FinalReview) -> list[list[str]]:
    report = review.report
    rows = []
    if (source := report.source_comparison) is not None:
        rows.append(
            [
                "source",
                verdict(source.verdict),
                basis(source.basis),
                digests(source.expected_swhid, source.observed_swhid),
            ]
        )
    if (environment := report.experiment_environment_comparison) is not None:
        packages = (
            f"{environment.matched} matched, {environment.missing_count} missing, {environment.extra_count} extra, "
            f"{environment.version_mismatch_count} versions differ"
            f'<br><span class="muted">{environment.expected_package_total} packages expected, '
            f"{environment.observed_package_total} observed, {environment.advisory_count} advisory</span><br>"
        )
        rows.append(
            [
                "experiment environment",
                verdict(environment.verdict),
                basis(environment.basis),
                packages + digests(environment.expected_artifact_digest, environment.observed_artifact_digest),
            ]
        )
    if (activation := report.activation_outcome) is not None:
        exit_code = "—" if activation.exit_code is None else str(activation.exit_code)
        rows.append(["activation", verdict(activation.verdict), basis(activation.basis), f"exit code {esc(exit_code)}"])
    for experiment in report.experiment_comparisons:
        check = (
            f"<code>{esc(experiment.verify_script_path)}</code> exited "
            f"{esc(experiment.observed_verify_exit_code)}, the author's "
            f"{esc(experiment.expected_verify_exit_code)}<br>"
        )
        rows.append(
            [
                f"experiment <code>{esc(experiment.experiment_name)}</code>",
                verdict(experiment.verdict),
                basis(experiment.basis),
                check + digests(experiment.expected_output_digest, experiment.observed_output_digest),
            ]
        )
    return rows


def package_rows(deltas: tuple[PackageDelta, ...]) -> list[list[str]]:
    return [
        [
            esc(delta.ecosystem),
            f"<code>{esc(delta.name)}</code>",
            esc(delta.expected_version or "—"),
            esc(delta.observed_version or "—"),
        ]
        for delta in deltas
    ]


def package_details(review: FinalReview) -> str:
    environment = review.report.experiment_environment_comparison
    if environment is None:
        return ""
    parts = [
        (label, deltas)
        for label, deltas in (
            ("missing", environment.missing),
            ("extra", environment.extra),
            ("versions differ", environment.version_mismatches),
        )
        if deltas
    ]
    return "".join(
        f"<details><summary>Packages {esc(label)}: {len(deltas)}</summary>"
        + table(["Ecosystem", "Package", "Expected", "Observed"], package_rows(deltas))
        + "</details>"
        for label, deltas in parts
    )


def review_body(review: FinalReview, test: ShowcaseTest) -> str:
    report = review.report
    status = f'<span class="{REVIEW_TONE[report.status]}">{esc(report.status)}</span>'
    signed = '<span class="ok">signed</span>' if review.signed else '<span class="muted">not signed</span>'
    cards = [
        ("Test", f"<code>{esc(test.test or '')}</code>"),
        ("Run", f"<code>{esc(test.run or '')}</code>"),
        ("Review", f"<code>{esc(report.review_id)}</code><br>{status} · {signed}"),
        (
            "Reviewed",
            f"<code>{esc(report.subject.name)}</code><br><code>{esc(report.subject.ree_digest or '—')}</code>",
        ),
        ("Machine", f"{esc(report.machine.system)} {esc(report.machine.architecture)}"),
        ("Opened", f"{esc(report.created_at)}<br>updated {esc(report.updated_at)}"),
    ]
    steps = "".join(
        f"<li><code>{esc(step.step)}</code> "
        f'<span class="{REVIEW_TONE[step.status]}">{esc(step.status)}</span>'
        + (f" {esc(step.failure)}" if step.failure else "")
        + "</li>"
        for step in report.steps
    )
    failure = f'<p class="no">{esc(report.failure)}</p>' if report.failure else ""
    rows = verdict_rows(review)
    return (
        '<div class="cards">'
        + "".join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in cards)
        + "</div>"
        + failure
        + "<h3>Verdicts</h3>"
        + (
            table(["Part", "Verdict", "Basis", "Evidence"], rows)
            if rows
            else '<p class="muted">The review reached no verdict.</p>'
        )
        + package_details(review)
        + "<h3>Steps</h3>"
        + (f"<ol>{steps}</ol>" if steps else '<p class="muted">The review took no step.</p>')
        + f'<p class="muted">Read from <code>{esc(source_name(review.source))}</code> at '
        f"<code>{esc(review.commit)}</code>.</p>"
    )


def review_section(showcase: Showcase, test: ShowcaseTest | None, review: FinalReview | None) -> str:
    title = "Final review"
    left = (
        f"The review the {esc(showcase.name)} showcase's test ran on a second machine from the sealed REE alone"
        if showcase.kind == "real_world"
        else f"The review the {esc(showcase.name)} showcase's review test left"
    )
    lede = (
        f"{left}, as its own history holds it at its last commit: a reviewer's verdict on each part of a sealed REE. "
        "A bundled basis checks against what the REE carries; an independent one rebuilds from the recorded origin "
        "and recipe."
    )
    if test is None:
        body = f'<p class="muted">This clone has no run of its {_test_named(showcase, "review")}.</p>'
    elif review is None:
        body = f'<p class="no">Its {_test_named(showcase, "review")} preserved no review.</p>'
    else:
        body = review_body(review, test)
    return section(review_anchor(showcase.name), title, lede, body)


def page_showcase_ree(
    showcase: Showcase,
    test: ShowcaseTest | None,
    ree: SealedRee | None,
    reviewing: ShowcaseTest | None,
    review: FinalReview | None,
) -> Page:
    title = f"{showcase.name} REE"
    lede = (
        f'The REE the <a href="showcase-gate.html#showcase-{esc(showcase.name)}">{esc(showcase.name)}</a> showcase\'s '
        f"{_test_named(showcase, 'authoring')} sealed, as the test preserved it. Each script is matched against what "
        "inference proposed in the REE's own history: written as inferred, chosen over what inference proposed, "
        "written where inference proposed nothing, or written without inference being asked. Where inference was "
        "asked, its decision graph shows the path its last answer took and what each check observed."
    )
    if test is None:
        body = f'<p class="muted">This clone has no run of its {_test_named(showcase, "authoring")}.</p>'
    elif ree is None:
        body = f'<p class="no">Its {_test_named(showcase, "authoring")} preserved no sealed REE.</p>'
    else:
        body = ree_body(ree, test)
    teaser = f"What {showcase.name}'s {_test_named(showcase, 'authoring')} sealed, and what its reviewer found"
    return Page(
        slug(showcase.name),
        title,
        teaser,
        section(slug(showcase.name), title, lede, body) + review_section(showcase, reviewing, review),
    )
