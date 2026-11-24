import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from repo2ree_repoview.overview.exports import (
    Behaviour,
    Campaign,
    CaseOrigin,
    CaseReplay,
    ExerciseCase,
    ExerciseProblem,
    Exercises,
    KeptFor,
    Move,
    Outcome,
    StepRun,
    Verdict,
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
        case KeptFor(kind="new_behaviours", behaviours=behaviours):
            return f"+{len(behaviours)} behaviours"
        case KeptFor(files=files):
            return f"+{sum(files.values())} arcs"


VERDICT_TONES = {"held": "ok", "violated": "no", "inconclusive": "ex"}
AGGREGATE_NAMES = {"Ree": "the REE", "Review": "a review"}
FIELD_VERBS = {("unset", "set"): "sets", ("set", "set"): "changes", ("set", "unset"): "clears"}
BEHAVIOURS_LEDE = (
    "A behaviour is one thing replaying a case did that the CLI-core specification names: a rule decided one way, "
    "an operation taking one edge of the REE's or a review's lifecycle or of one of their fields, or a command "
    "ending one way. The specification declares each rule held and each edge by each operation that may take it; a "
    "search keeps a case that covers behaviours, or code arcs, no other case does. A violated rule or a command's "
    "outcome is covered too, though nothing declares it."
)
CASE_BEHAVIOURS_LEDE = (
    "What replaying this case did, as the specification names it; <em>only here</em>: no other case does."
)


BETWEEN_OPERATIONS = "(between operations)"


def _operation(name: str) -> str:
    return "a change outside ree" if name == BETWEEN_OPERATIONS else f"<code>{esc(name)}</code>"


def _move_label(move: Move) -> str:
    whose = AGGREGATE_NAMES.get(move.aggregate, esc(move.aggregate))
    if move.part == "lifecycle":
        if move.source == "(none)":
            return f"{_operation(move.operation)} makes {whose}, {esc(move.target)}"
        return f"{_operation(move.operation)} takes {whose} from {esc(move.source)} to {esc(move.target)}"
    field = f"{whose}'s <code>{esc(move.machine)}</code>"
    if move.source == "(none)":
        return f"{_operation(move.operation)} starts {field} {esc(move.target)}"
    if verb := FIELD_VERBS.get((move.source, move.target)):
        return f"{_operation(move.operation)} {verb} {field}"
    return f"{_operation(move.operation)} takes {field} from {esc(move.source)} to {esc(move.target)}"


def behaviour_label(behaviour: Behaviour) -> str:
    match behaviour:
        case Verdict(rule=rule, verdict=verdict):
            return f'{rule_link(rule)} <span class="{VERDICT_TONES[verdict]}">{verdict}</span>'
        case Move() as move:
            return _move_label(move)
        case Outcome(command=command, status=None):
            return f"<code>ree {esc(command)}</code> ended without a result"
        case Outcome(command=command, status=status, category=category):
            failure = f" ({esc(category)})" if category else ""
            return f"<code>ree {esc(command)}</code> {esc(status)}{failure}"


def _key(behaviour: Behaviour) -> tuple[int, str]:
    return ("verdict", "move", "outcome").index(behaviour.kind), behaviour.model_dump_json()


def _ordered(behaviours: set[Behaviour]) -> list[Behaviour]:
    return sorted(behaviours, key=_key)


def behaviours_overview(exercises: Exercises) -> str:
    by_behaviour: dict[Behaviour, list[str]] = {}
    for case in exercises.cases:
        for behaviour in case.behaviours.behaviours:
            by_behaviour.setdefault(behaviour, []).append(case.digest)
    declared = set(exercises.declared)
    covered = declared & set(by_behaviour)
    beyond = set(by_behaviour) - declared
    summary = (
        f"<p>{len(covered)} of the {len(declared)} declared behaviours covered, "
        f"and {len(beyond)} more that nothing declares.</p>"
    )
    rows = [
        [
            behaviour_label(behaviour),
            str(len(by_behaviour[behaviour])),
            " ".join(case_link(digest) for digest in by_behaviour[behaviour][:6])
            + (" &hellip;" if len(by_behaviour[behaviour]) > 6 else ""),
        ]
        for behaviour in _ordered(set(by_behaviour))
    ]
    gaps = _ordered(declared - set(by_behaviour))
    missing = (
        f"<h3>Declared, covered by no case ({len(gaps)})</h3><ul>"
        + "".join(f"<li>{behaviour_label(behaviour)}</li>" for behaviour in gaps)
        + "</ul>"
        if gaps
        else ""
    )
    listed = table(["Behaviour", "Cases", "Covered by"], rows, "behaviours-table")
    return summary + filter_box("behaviours-table", "filter") + f'<div class="table-scroll">{listed}</div>' + missing


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


def _kept_case(digest: str, present: frozenset[str]) -> str:
    if digest in present:
        return case_link(digest)
    return f'<code>{esc(digest)}</code> <span class="muted">removed</span>'


def campaigns_table(found: Sequence[Campaign], present: frozenset[str]) -> str:
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
            "<br>".join(f"{_kept_case(item.case, present)} {kept_for(item.kept_for)}" for item in campaign.kept),
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
    return f"{sum(found.arcs for found in files)} (+{sum(found.unique for found in files)})"


def measured(case: ExerciseCase) -> str:
    coverage = case.coverage
    if coverage is None:
        return '<span class="muted">not measured</span>'
    commit = f"<code>{esc(coverage.commit[:8])}</code>" + (' <span class="ex">dirty</span>' if coverage.dirty else "")
    changed = [found.path for found in coverage.files if found.stale]
    if not changed:
        return f'{commit} <span class="ok" title="no file it executes changed since">current</span>'
    tip = f"{len(changed)} file{'s' if len(changed) != 1 else ''} it executes changed since: " + ", ".join(changed)
    return f'{commit} <span class="ex" title="{esc(tip)}">stale</span>'


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
            f"{len(case.behaviours.behaviours)} (+{len(case.unique_behaviours)})",
            _arcs(case),
            measured(case),
        ]
        for case in found
    ]
    headers = ["Case", "Origin", "REEs", "Steps", "Drifts", "Faults", "Expects", "Behaviours", "Arcs", "Measured at"]
    return filter_box("cases", "filter") + f'<div class="table-scroll">{table(headers, rows, "cases")}</div>'


def page_exercises(exercises: Exercises) -> Page:
    recorded = frozenset(campaign.run for campaign in exercises.campaigns)
    body = (
        "<h1>Exercises</h1>"
        + section(
            "campaigns",
            "Search campaigns",
            "",
            campaigns_table(exercises.campaigns, frozenset(case.digest for case in exercises.cases)),
        )
        + section("behaviours", "Covered behaviours", BEHAVIOURS_LEDE, behaviours_overview(exercises))
        + section("cases", "Cases", "", cases_table(exercises.cases, recorded))
    )
    covered = {behaviour for case in exercises.cases for behaviour in case.behaviours.behaviours}
    return Page(EXERCISES, "Exercises", f"{len(exercises.cases)} cases, {len(covered)} behaviours", body)


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


def behaviours_section(case: ExerciseCase) -> str:
    unique = set(case.unique_behaviours)
    found = _ordered(set(case.behaviours.behaviours))
    body = (
        "<ul>"
        + "".join(
            f"<li>{behaviour_label(behaviour)}"
            + (' <span class="ex">only here</span>' if behaviour in unique else "")
            + "</li>"
            for behaviour in found
        )
        + "</ul>"
        if found
        else ""
    )
    if case.replay is not None and set(case.replay.behaviours) != set(case.behaviours.behaviours):
        gained = _ordered(set(case.replay.behaviours) - set(case.behaviours.behaviours))
        lost = _ordered(set(case.behaviours.behaviours) - set(case.replay.behaviours))
        body += (
            '<p class="ex">Its newest replay covers otherwise: '
            f"+{', '.join(map(behaviour_label, gained)) or 'nothing'}; "
            f"&minus;{', '.join(map(behaviour_label, lost)) or 'nothing'}</p>"
        )
    return section(
        "behaviours", "Covered behaviours", CASE_BEHAVIOURS_LEDE, body or '<p class="muted">None recorded.</p>'
    )


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
        + behaviours_section(case)
        + coverage_section(case)
    )
    return Page(case_slug(case.digest), f"Exercise {case.digest}", "", body)
