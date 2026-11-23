import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from repo2ree_repoview.overview.exports import (
    Campaign,
    CaseOrigin,
    CaseReplay,
    ExerciseCase,
    ExerciseProblem,
    Exercises,
    KeptFor,
    StepRun,
)
from repo2ree_repoview.overview.html import Page, esc, filter_box, in_frame, rule_link, section, table

EXERCISES = "exercises"
ENVIRONMENT = "environment"
GUTTER, LANE, RIGHT, ROW, TOP = 44, 190, 40, 28, 52


def case_slug(digest: str) -> str:
    return f"{EXERCISES}/{digest}"


def session_target(digest: str) -> str:
    return f"evidence/{EXERCISES}/{digest}/session/index.html"


def case_link(digest: str) -> str:
    return f'<a href="{case_slug(digest)}.html"><code>{esc(digest)}</code></a>'


def _when(value: str | None) -> str:
    if value is None:
        return '<span class="muted">running</span>'
    return esc(datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M"))


def _duration(campaign: Campaign) -> str:
    if campaign.ended is None:
        return "&ndash;"
    seconds = (datetime.fromisoformat(campaign.ended) - datetime.fromisoformat(campaign.started)).total_seconds()
    hours, rest = divmod(int(seconds), 3600)
    return f"{hours} h {rest // 60} min" if hours else f"{rest // 60} min {rest % 60} s"


def kept_for(found: KeptFor | None) -> str:
    match found:
        case None:
            return "&ndash;"
        case KeptFor(kind="showed_problems"):
            return '<span class="no">new problem</span>'
        case KeptFor(kind="new_reached", items=items):
            return f"+{len(items)} spec"
        case KeptFor(files=files):
            return f"+{sum(files.values())} arcs"


def origin(found: CaseOrigin, recorded: frozenset[str] = frozenset()) -> str:
    if found.kind == "hand_written":
        return "hand-written"
    search = f"<code>{esc(found.search)}</code>"
    if found.run in recorded:
        search = f'<a href="{EXERCISES}.html#campaign-{esc(found.run)}">{search}</a>'
    return f"{search} {kept_for(found.kept_for)}"


def expects(case: ExerciseCase) -> str:
    if case.expects.kind == "conforms":
        return '<span class="ok">conforms</span>'
    rules = sorted({problem.rule for problem in case.expects.problems})
    return '<span class="no">shows</span> ' + ", ".join(rule_link(rule) for rule in rules)


def _exit(campaign: Campaign) -> str:
    if campaign.exit is None:
        return '<span class="muted">running</span>'
    return '<span class="ok">0</span>' if campaign.exit == 0 else f'<span class="no">{campaign.exit}</span>'


CAMPAIGN_HEADERS = [
    "Started",
    "Search",
    "Machine",
    "Commit",
    "Took",
    "Workers",
    "Examples",
    "Steps",
    "Rounds (found)",
    "Kept",
    "Unconfirmed",
    "Exit",
]


def campaigns_table(found: Sequence[Campaign]) -> str:
    if not found:
        return '<p class="muted">None recorded.</p>'
    rows = [
        [
            f'<span id="campaign-{esc(campaign.run)}">{_when(campaign.started)}</span>',
            f"<code>{esc(campaign.search)}</code>",
            esc(campaign.machine or "here"),
            f"<code>{esc(campaign.commit[:8])}</code>" + (' <span class="ex">dirty</span>' if campaign.dirty else ""),
            _duration(campaign),
            str(campaign.settings.workers),
            str(campaign.settings.examples),
            str(campaign.settings.steps),
            f"{campaign.rounds} ({campaign.rounds_found})",
            "<br>".join(f"{case_link(item.case)} {kept_for(item.kept_for)}" for item in campaign.kept),
            str(campaign.unconfirmed),
            _exit(campaign),
        ]
        for campaign in found
    ]
    return f'<div class="table-scroll">{table(CAMPAIGN_HEADERS, rows, "campaigns")}</div>'


def _arcs(case: ExerciseCase) -> str:
    if case.coverage is None:
        return "&ndash;"
    files = case.coverage.files
    stale = ' <span class="ex">stale</span>' if any(found.stale for found in files) else ""
    return f"{sum(found.arcs for found in files)} (+{sum(found.unique for found in files)}){stale}"


def cases_table(found: Sequence[ExerciseCase], recorded: frozenset[str]) -> str:
    rows = [
        [
            case_link(case.digest),
            origin(case.origin, recorded),
            esc(", ".join(case.rees)),
            str(len(case.steps)),
            str(len(case.drifts)),
            str(len(case.faults)),
            expects(case),
            f"{len(case.reached.items)} (+{len(case.unique_reached)})",
            _arcs(case),
            _when(case.replay.when) if case.replay else "&ndash;",
        ]
        for case in found
    ]
    headers = ["Case", "Origin", "REEs", "Steps", "Drifts", "Faults", "Expects", "Spec", "Arcs", "Replayed"]
    return filter_box("cases", "filter") + f'<div class="table-scroll">{table(headers, rows, "cases")}</div>'


def page_exercises(exercises: Exercises) -> Page:
    recorded = frozenset(campaign.run for campaign in exercises.campaigns)
    body = (
        "<h1>Exercises</h1>"
        + section("campaigns", "Search campaigns", "", campaigns_table(exercises.campaigns))
        + section("cases", "Cases", "", cases_table(exercises.cases, recorded))
    )
    return Page(EXERCISES, "Exercises", f"{len(exercises.cases)} cases", body)


def _set(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _set(inner) for key, inner in value.items() if inner not in (None, [], {})}
    return value


def _parameters(entry: dict[str, Any], *skip: str) -> str:
    shown = _set({key: value for key, value in entry.items() if key not in skip})
    return f"<code>{esc(json.dumps(shown, ensure_ascii=False))}</code>" if shown else ""


def steps_section(case: ExerciseCase) -> str:
    rows = [
        [
            str(index),
            esc(step.get("ree")),
            f"<code>{esc(step.get('operation'))}</code>",
            _parameters(step, "ree", "operation"),
        ]
        for index, step in enumerate(case.steps)
    ]
    body = table(["#", "REE", "Operation", "Values"], rows)
    if case.drifts:
        drifts = [
            [esc(drift.get("before")), esc(drift.get("ree")), _parameters(drift, "before", "ree")]
            for drift in case.drifts
        ]
        body += "<h3>Drifts</h3>" + table(["Before", "REE", "Change"], drifts)
    if case.faults:
        body += "<h3>Faults</h3>" + table(["Fault"], [[_parameters(fault)] for fault in case.faults])
    return section("steps", "Steps", "", body)


def _arrow(x1: float, x2: float, label: str, tone: str) -> str:
    way = 1 if x2 > x1 else -1
    tip = x2 - way * 7
    return (
        f'<g class="{tone}"><line x1="{x1 + way * 6}" y1="0" x2="{tip}" y2="0" stroke="currentColor" '
        f'stroke-width="1.6"/><path d="M{tip + way} -4 L{x2 - way} 0 L{tip + way} 4 Z" fill="currentColor"/>'
        f'<text x="{min(x1, x2) + 10}" y="-6">{esc(label)}</text></g>'
    )


def _note(x: float, label: str, tone: str) -> str:
    return (
        f'<g class="{tone}"><circle cx="{x}" cy="0" r="4.5" fill="currentColor"/>'
        f'<text x="{x + 10}" y="4">{esc(label)}</text></g>'
    )


def _tone(run: StepRun | None) -> str:
    if run is None or run.status is None:
        return "muted"
    return {"succeeded": "ok", "failed": "no"}.get(run.status, "ex")


def sequence(case: ExerciseCase, replay: CaseReplay | None) -> str:
    lanes = [ENVIRONMENT, *case.rees]
    x = {lane: GUTTER + index * LANE + LANE / 2 for index, lane in enumerate(lanes)}
    ran = {run.step: run for run in replay.steps} if replay else {}
    rows: list[tuple[str, str]] = []
    for index, step in enumerate(case.steps):
        ree = str(step.get("ree"))
        rows.extend(
            ("", _note(x[str(drift["ree"])], f"drift: {drift.get('kind', '')}", "ex"))
            for drift in case.drifts
            if drift.get("before") == index and drift.get("ree") in x
        )
        if step.get("operation") == "load_ree_bundle" and step.get("exported_by") in x:
            damage = step.get("corruption")
            label = "bundle" + (f" ({damage})" if damage and damage != "intact" else "")
            rows.append(("", _arrow(x[str(step["exported_by"])], x[ree], label, "p-journal")))
        run = ran.get(index)
        outcome = f" → {run.status}" if run and run.status else ""
        rows.append((str(index), _arrow(x[ENVIRONMENT], x[ree], f"{step.get('operation')}{outcome}", _tone(run))))
    width = GUTTER + len(lanes) * LANE + RIGHT
    height = TOP + len(rows) * ROW + 12
    parts = [
        f'<line x1="{x[lane]}" y1="{TOP - 12}" x2="{x[lane]}" y2="{height - 6}" stroke="var(--line)" '
        'stroke-width="1.5"/>'
        f'<text class="lane-name" x="{x[lane]}" y="{TOP - 20}" text-anchor="middle">{esc(lane)}</text>'
        for lane in lanes
    ]
    for number, (shown, drawn) in enumerate(rows):
        y = TOP + number * ROW + ROW / 2
        if shown:
            parts.append(f'<text class="t" x="{GUTTER - 10}" y="{y + 4}" text-anchor="end">{shown}</text>')
        parts.append(f'<g transform="translate(0 {y})">{drawn}</g>')
    return (
        f'<div class="seq-panel"><svg class="seq" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="exercise {esc(case.digest)}" style="width:{width}px;min-width:{width}px">'
        f"{''.join(parts)}</svg></div>"
    )


def _problems(problems: Sequence[ExerciseProblem]) -> str:
    rows = [
        [
            "" if problem.step is None else str(problem.step),
            rule_link(problem.rule) if problem.kind == "violated" else f"<code>{esc(problem.rule)}</code>",
            esc(problem.subject),
            esc(problem.detail),
        ]
        for problem in problems
    ]
    return table(["Step", "Rule", "Subject", "Detail"], rows)


def sequence_section(case: ExerciseCase) -> str:
    body = sequence(case, case.replay)
    if case.replay is not None and case.replay.problems:
        body += "<h3>Problems</h3>" + _problems(case.replay.problems)
    return section("sequence", "Sequence", "", body)


def _item(item: str, unique: set[str]) -> str:
    only = ' <span class="ex">only here</span>' if item in unique else ""
    shown = rule_link(item) if " " not in item else f"<code>{esc(item)}</code>"
    return f"<li>{shown}{only}</li>"


def spec_section(case: ExerciseCase) -> str:
    unique = set(case.unique_reached)
    rules = [item for item in case.reached.items if " " not in item]
    transitions = [item for item in case.reached.items if " " in item]
    body = (
        f"<h3>Rules ({len(rules)})</h3><ul>{''.join(_item(item, unique) for item in rules)}</ul>"
        f"<h3>Transitions ({len(transitions)})</h3><ul>{''.join(_item(item, unique) for item in transitions)}</ul>"
    )
    if case.replay is not None and set(case.replay.reached) != set(case.reached.items):
        gained = sorted(set(case.replay.reached) - set(case.reached.items))
        lost = sorted(set(case.reached.items) - set(case.replay.reached))
        body += (
            f'<p class="ex">Replay differs: +{esc(", ".join(gained) or "nothing")}; '
            f"&minus;{esc(', '.join(lost) or 'nothing')}</p>"
        )
    return section("spec", "Specification coverage", "", body)


def coverage_section(case: ExerciseCase) -> str:
    coverage = case.coverage
    if coverage is None:
        return section("branches", "Branch coverage", "", '<p class="muted">Not measured.</p>')
    rows = [
        [
            f"<code>{esc(found.path)}</code>",
            str(found.arcs),
            f'<span class="ex">{found.unique}</span>' if found.unique else "0",
            '<span class="ex">stale</span>' if found.stale else "",
        ]
        for found in sorted(coverage.files, key=lambda found: (-found.unique, found.path))
    ]
    dirty = " (dirty)" if coverage.dirty else ""
    measured = f'<p class="muted">At <code>{esc(coverage.commit[:8])}</code>{dirty}</p>'
    files = table(["File", "Arcs", "Only here", "Stale"], rows, "branches-table")
    return section(
        "branches",
        "Branch coverage",
        "",
        measured + filter_box("branches-table", "filter") + f'<div class="table-scroll">{files}</div>',
    )


def _facts(case: ExerciseCase, session: bool) -> str:
    replayed = _when(case.replay.when) if case.replay else "&ndash;"
    shown = f'<a href="{esc(in_frame(session_target(case.digest), EXERCISES))}">session</a>' if session else "&ndash;"
    rows = [
        ["Origin", origin(case.origin)],
        ["Expects", expects(case)],
        ["REEs", esc(", ".join(case.rees))],
        ["Replayed", replayed],
        ["Session", shown],
    ]
    return table(["", ""], rows)


def page_exercise(case: ExerciseCase, *, session: bool = False) -> Page:
    body = (
        f'<p class="muted"><a href="{EXERCISES}.html">Exercises</a> /</p>'
        f"<h1>Exercise <code>{esc(case.digest)}</code></h1>"
        + _facts(case, session)
        + steps_section(case)
        + sequence_section(case)
        + spec_section(case)
        + coverage_section(case)
    )
    return Page(case_slug(case.digest), f"Exercise {case.digest}", "", body)
