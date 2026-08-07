"""Render how one REE's evidence stood after each authoring act.

``evidence_graph.py`` draws the rules — which step rests on which, and what
would stale it. This draws a run against those rules: the api-integration tier
snapshots ``GET /rees/{id}/state`` after every act, and each snapshot carries
the audit, which is derived rather than stored and so exists nowhere else once
the run is over.

One row per audited step, one column per frame, and the cell is what the audit
said at that moment. Read across a row to see one step's evidence appear and,
where it happens, stop speaking for the REE; read down a column to see what a
single act changed. Cells that differ from the frame before them are ticked, so
the transitions — the part a table of verdicts buries — are what the eye lands
on.

    python scripts/ree_filmstrip.py                                # SVG on stdout
    python scripts/ree_filmstrip.py -o dist/diagrams/domain/ree-filmstrip.svg
    python scripts/ree_filmstrip.py --frames path/to/capture.ndjson
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CAPTURE = REPO_ROOT / "test-artifacts/ree-snapshots/api-integration/test_full_authoring_pipeline.ndjson"

# The audited steps, in the order ReeAudit declares them — which is also the
# order they can first become applicable, so the matrix reads as a staircase
# rather than needing a hand-kept sequence here.
STEP_FIELDS = (
    "source",
    "evaluation",
    "hardware",
    "runtime",
    "sbom",
    "sbom_cross_check",
    "test_activation",
)

# ================================================
# Geometry
# ================================================
# SVG has no layout engine, so every position is arithmetic and labels are
# measured against an assumed advance width, as in trace_journal.py.

MARGIN = 18
CELL_W = 30
CELL_H = 22
GAP = 3
NAME_GAP = 14
LEGEND_H = 34
ROW_FS = 11.0
HEAD_FS = 10.0
CHAR_W = 0.6
HEAD_TILT = 0.707  # cos(45°): a rotated label's vertical reach

# ================================================
# Palette
# ================================================
# Shared with the evidence graph, so a step means the same colour in both. The
# three standings that carry evidence form one ramp — absent, declared, held —
# and stale leaves it deliberately: it is not "more" or "less" than current, it
# is a different kind of answer.

INK = "#16202a"
INK_SOFT = "#5a6b78"
GROUND = "#ffffff"

FILLS = {
    "not_applicable": "#f2f5f7",
    "missing": "#ffffff",
    "current": "#2d6b8c",
    "stale": "#c8862a",
}
STROKES = {
    "not_applicable": "#e6ebef",
    "missing": "#c3d0da",
    "current": "#2d6b8c",
    "stale": "#a86a1b",
}
DECLARED = "#0f766e"


@dataclass
class Frame:
    label: str
    status: str
    verdicts: dict[str, str]
    ree: dict[str, Any] = field(default_factory=dict)
    produced_receipt: bool = False


@dataclass
class Row:
    name: str
    cells: list[str] = field(default_factory=list)
    kind: str = "step"  # step | experiment


def load_frames(path: Path) -> list[Frame]:
    """Read the capture into the two things the emitters draw from.

    The verdicts are what the matrix shows; the aggregate itself is what the
    timeline diffs. File metadata stays in the capture rather than being
    mirrored here — the file is the record, these are views of it.
    """
    frames: list[Frame] = []
    previous_runs: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        state = raw["state"]
        audit = state["audit"]

        verdicts = {field_: audit[field_]["evidence"] for field_ in STEP_FIELDS}
        for experiment in audit.get("experiments") or []:
            verdicts[f"experiment:{experiment['name']}"] = experiment["run"]["evidence"]

        # Whether this act ran something, derived rather than read off the
        # label: a frame that minted or replaced a receipt is a run, and one
        # that did not is authoring. Taking it from the label would mean the
        # picture believed the test's prose instead of the REE.
        runs = _receipt_runs(state["ree"])
        produced = runs != previous_runs
        previous_runs = runs

        frames.append(
            Frame(
                label=str(raw["label"]),
                status=str(state.get("status", "")),
                verdicts=verdicts,
                ree=state["ree"],
                produced_receipt=produced,
            )
        )
    return frames


def _receipt_runs(ree: dict[str, Any]) -> dict[str, str]:
    """The run that produced each receipt the REE currently holds."""
    receipts = ree["subject"]["receipts"]
    runs: dict[str, str] = {}
    for name, receipt in receipts.items():
        if name == "experiments":
            for experiment_name, entry in (receipt or {}).items():
                runs[f"experiment:{experiment_name}"] = entry["run_id"]
        elif receipt is not None:
            runs[name] = receipt["run_id"]
    return runs


def build_rows(frames: list[Frame]) -> list[Row]:
    """One row per step, plus one per experiment that is ever declared.

    An experiment absent from a frame's audit is not missing evidence — it has
    not been declared yet — so its cells read ``not_applicable`` until the
    declaration brings it into being. That keeps the row honest about when the
    experiment started existing rather than implying it was owed all along.
    """
    rows = [Row(name=field_) for field_ in STEP_FIELDS]
    experiments = sorted({key for frame in frames for key in frame.verdicts if key.startswith("experiment:")})
    rows.extend(Row(name=key, kind="experiment") for key in experiments)
    for row in rows:
        row.cells = [frame.verdicts.get(row.name, "not_applicable") for frame in frames]
    return rows


def render_svg(frames: list[Frame], rows: list[Row]) -> str:
    if not frames:
        raise SystemExit("capture holds no frames")

    labels = [_row_label(row) for row in rows]
    name_w = max(len(label) for label in labels) * ROW_FS * CHAR_W + NAME_GAP
    head_h = max(len(frame.label) for frame in frames) * HEAD_FS * CHAR_W * HEAD_TILT + 10
    grid_w = len(frames) * (CELL_W + GAP) - GAP
    grid_h = len(rows) * (CELL_H + GAP) - GAP
    width = MARGIN * 2 + name_w + grid_w
    height = MARGIN * 2 + head_h + grid_h + LEGEND_H

    grid_x = MARGIN + name_w
    grid_y = MARGIN + head_h

    out: list[str] = [
        f'<svg class="ree-filmstrip" viewBox="0 0 {width:.0f} {height:.0f}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="{GROUND}"/>',
        '<g font-family="Helvetica, Arial, sans-serif">',
    ]

    # Column headings, tilted because "sbom cross-check" is wider than its
    # column and always will be — the labels are the acts' own names.
    for index, frame in enumerate(frames):
        x = grid_x + index * (CELL_W + GAP) + CELL_W / 2
        y = grid_y - 6
        colour = INK if frame.produced_receipt else DECLARED
        weight = "500" if frame.produced_receipt else "400"
        out.append(
            f'<text x="{x:.1f}" y="{y:.1f}" transform="rotate(-45 {x:.1f} {y:.1f})" '
            f'font-size="{HEAD_FS}" fill="{colour}" font-weight="{weight}">{escape(frame.label)}</text>'
        )

    for r, (row, label) in enumerate(zip(rows, labels, strict=True)):
        y = grid_y + r * (CELL_H + GAP)
        out.append(
            f'<text x="{grid_x - NAME_GAP / 2:.1f}" y="{y + CELL_H / 2 + 3.8:.1f}" '
            f'font-size="{ROW_FS}" fill="{INK}" text-anchor="end" '
            f'font-family="ui-monospace, Menlo, monospace">{escape(label)}</text>'
        )
        for c, standing in enumerate(row.cells):
            x = grid_x + c * (CELL_W + GAP)
            out.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL_W}" height="{CELL_H}" rx="2" '
                f'fill="{FILLS[standing]}" stroke="{STROKES[standing]}" stroke-width="1"/>'
            )
            # The tick is the whole point of a filmstrip over a table of
            # verdicts: almost every cell repeats the one before it, and the
            # few that do not are the story.
            if c and standing != row.cells[c - 1]:
                out.append(
                    f'<rect x="{x - 1.5:.1f}" y="{y - 1.5:.1f}" width="2.5" height="{CELL_H + 3}" fill="{INK}"/>'
                )

    out.append(_legend(MARGIN, grid_y + grid_h + 22))
    out.extend(["</g>", "</svg>"])
    return "\n".join(out)


def _row_label(row: Row) -> str:
    return row.name.removeprefix("experiment:") + " (exp)" if row.kind == "experiment" else row.name


def _legend(x: float, y: float) -> str:
    parts = []
    cursor = x
    for standing in ("not_applicable", "missing", "current", "stale"):
        parts.append(
            f'<rect x="{cursor:.1f}" y="{y - 9:.1f}" width="16" height="12" rx="2" '
            f'fill="{FILLS[standing]}" stroke="{STROKES[standing]}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{cursor + 21:.1f}" y="{y:.1f}" font-size="9.5" fill="{INK_SOFT}">'
            f"{standing.replace('_', ' ')}</text>"
        )
        cursor += 21 + len(standing) * 9.5 * CHAR_W + 20
    parts.append(
        f'<rect x="{cursor:.1f}" y="{y - 10:.1f}" width="2.5" height="14" fill="{INK}"/>'
        f'<text x="{cursor + 9:.1f}" y="{y:.1f}" font-size="9.5" fill="{INK_SOFT}">'
        "changed from the frame before</text>"
    )
    return "".join(parts)


# ================================================
# The aggregate, field by field
# ================================================

# Lists the REE keys by identity rather than position. Without this, declaring a
# second experiment renumbers the first and the diff reports every field of both
# as changed — an artefact of the encoding, not of anything that happened.
KEYED_LISTS = {
    "subject.contents.entries": "path",
    "subject.definition.experiments": "name",
    # By identifier rather than name: an author correcting a spelling should
    # report as one changed field, not as one contributor leaving and another
    # arriving. The path it produces is long, and being stable is worth it.
    "subject.definition.catalog.contributors": "identifier",
}

# The areas an REE changes in, in the order the aggregate declares them. A frame
# usually touches one, and naming which is most of what makes a diff readable.
AREAS = ("definition", "receipts", "contents", "seal")

_DIGEST_KEEP = 14


@dataclass
class Change:
    area: str
    path: str
    old: str = ""
    new: str = ""

    @property
    def kind(self) -> str:
        return "added" if not self.old else "changed"


def flatten(node: Any, prefix: str = "", out: dict[str, Any] | None = None) -> dict[str, Any]:
    """The aggregate as dotted paths to leaves, with absent fields left out.

    ``None`` is dropped rather than recorded, because in this model it means
    "not yet" — an unfilled receipt slot, an undeclared source. Keeping it as a
    value made every slot that got filled report as one removal plus a dozen
    additions, which describes the JSON encoding rather than the REE: nothing
    was removed, a thing came into existence.
    """
    out = {} if out is None else out
    if isinstance(node, dict):
        for key, value in node.items():
            flatten(value, f"{prefix}.{key}" if prefix else key, out)
    elif isinstance(node, list):
        identity = KEYED_LISTS.get(prefix)
        if identity and all(isinstance(item, dict) and identity in item for item in node):
            for item in node:
                flatten(item, f"{prefix}[{item[identity]}]", out)
        else:
            out[prefix] = node
    elif node is not None:
        out[prefix] = node
    return out


def diff_frames(frames: list[Frame]) -> list[list[Change]]:
    """What each act changed about the aggregate, one list per frame."""
    diffs: list[list[Change]] = []
    previous: dict[str, Any] = {}
    for frame in frames:
        current = flatten(frame.ree)
        changes = [
            Change(_area(path), path, _show(previous.get(path)) if path in previous else "", _show(value))
            for path, value in current.items()
            if path not in previous or previous[path] != value
        ]
        # Nothing is ever removed on the authoring path — a receipt slot goes
        # from absent to filled and stays. A removal here would mean the REE
        # dropped a declaration, which `remove_source` can do, so it is reported
        # rather than assumed impossible.
        changes.extend(
            Change(_area(path), path, _show(value), "") for path, value in previous.items() if path not in current
        )
        diffs.append(sorted(changes, key=lambda change: (AREAS.index(change.area), change.path)))
        previous = current
    return diffs


def _area(path: str) -> str:
    parts = path.split(".")
    if parts[0] == "seal":
        return "seal"
    return parts[1] if len(parts) > 1 and parts[1] in AREAS else "definition"


def _show(value: Any) -> str:
    """One field's value, short enough to sit on a line.

    Digests are truncated because only their *difference* is legible anyway:
    fourteen characters distinguish any two this system will hold, and the full
    sixty-four turn every receipt into a wall.
    """
    if isinstance(value, str) and value.startswith("sha256:") and len(value) > _DIGEST_KEEP:
        return value[:_DIGEST_KEEP] + "…"
    if isinstance(value, list):
        return f"[{len(value)} items]" if len(value) > 3 else json.dumps(value)
    if isinstance(value, bool) or value is None or value == "":
        return json.dumps(value)
    return str(value)


def render_timeline(frames: list[Frame], diffs: list[list[Change]]) -> str:
    """The aggregate's field-by-field history, as a page.

    HTML rather than SVG for the reason trace_journal gives its own html
    emitter: this is text, and a browser measures text better than the
    arithmetic above can. It is also the form where a reader can select a digest
    and search for a field name.
    """
    sections: list[str] = []
    for frame, changes in zip(frames, diffs, strict=True):
        kind = "ran" if frame.produced_receipt else "authored"
        added = sum(1 for change in changes if change.kind == "added")
        changed = len(changes) - added
        counts = f"{added} new, {changed} changed"
        rows: list[str] = []
        for area in AREAS:
            in_area = [change for change in changes if change.area == area]
            if not in_area:
                continue
            rows.append(f'<tr class="area"><td colspan="3">{area}</td></tr>')
            for change in in_area:
                path = escape(change.path.removeprefix("subject.").removeprefix(f"{area}."))
                if change.kind == "added":
                    rows.append(
                        f'<tr><td class="mark add">+</td><td class="path">{path}</td>'
                        f'<td class="val">{escape(change.new)}</td></tr>'
                    )
                elif change.new:
                    rows.append(
                        f'<tr><td class="mark mod">~</td><td class="path">{path}</td>'
                        f'<td class="val"><s>{escape(change.old)}</s> → {escape(change.new)}</td></tr>'
                    )
                else:
                    rows.append(
                        f'<tr><td class="mark del">-</td><td class="path">{path}</td>'
                        f'<td class="val"><s>{escape(change.old)}</s></td></tr>'
                    )
        body = f"<table>{''.join(rows)}</table>" if rows else '<p class="quiet">nothing changed</p>'
        sections.append(
            f'<section><h2><span class="kind {kind}">{kind}</span>'
            f'{escape(frame.label)}<span class="counts">{counts}</span></h2>{body}</section>'
        )
    return _TIMELINE_PAGE.format(sections="\n".join(sections), frames=len(frames))


_TIMELINE_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>REE evidence timeline</title>
<style>
  :root {{
    --ground:#fbfcfd; --ink:#16202a; --soft:#5a6b78; --line:#dde4ea;
    --add:#0f766e; --mod:#a86a1b; --del:#9b2c2c; --accent:#2d6b8c;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --ground:#10161c; --ink:#dde5ec; --soft:#8b9aa7; --line:#26343f;
             --add:#4fb3a5; --mod:#e0a355; --del:#e08585; --accent:#6ab3d8; }}
  }}
  body {{ background:var(--ground); color:var(--ink); margin:0;
         font:13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
         padding:2.5rem 1.5rem 4rem; }}
  .page {{ max-width:64rem; margin:0 auto; }}
  h1 {{ font-size:1.1rem; margin:0 0 .3rem; }}
  .lede {{ color:var(--soft); margin:0 0 2rem; font-size:.82rem; }}
  section {{ border-top:1px solid var(--line); padding:1.1rem 0; }}
  h2 {{ font-size:.9rem; margin:0 0 .6rem; display:flex; align-items:baseline; gap:.7rem; }}
  .kind {{ font-size:.62rem; text-transform:uppercase; letter-spacing:.1em;
          border:1px solid currentColor; border-radius:2px; padding:.05em .4em; }}
  .kind.ran {{ color:var(--accent); }}
  .kind.authored {{ color:var(--add); }}
  .counts {{ margin-left:auto; color:var(--soft); font-size:.72rem; font-weight:400; }}
  table {{ border-collapse:collapse; width:100%; }}
  td {{ padding:.12rem .5rem .12rem 0; vertical-align:baseline; }}
  tr.area td {{ color:var(--soft); font-size:.68rem; text-transform:uppercase;
               letter-spacing:.1em; padding-top:.7rem; }}
  .mark {{ width:1.2em; font-weight:600; }}
  .mark.add {{ color:var(--add); }}
  .mark.mod {{ color:var(--mod); }}
  .mark.del {{ color:var(--del); }}
  .path {{ white-space:nowrap; padding-right:1.4rem; }}
  .val {{ color:var(--soft); word-break:break-all; }}
  s {{ text-decoration-color:var(--del); opacity:.75; }}
  .quiet {{ color:var(--soft); margin:0; }}
</style>
<div class="page">
  <h1>REE evidence timeline</h1>
  <p class="lede">
    Every field of the aggregate that changed, across {frames} frames of one authoring run.
    Digests are shown to fourteen characters. Absent fields are omitted rather than shown null.
  </p>
{sections}
</div>
"""


# ================================================
# The finished REE, browsable
# ================================================


def digest_index(ree: dict[str, Any]) -> dict[str, tuple[str, int]]:
    """Every distinct digest in the aggregate, labelled and counted.

    This is the one thing a general JSON viewer cannot give an REE. A sealed
    aggregate here holds fourteen distinct digests across thirty-one places, and
    the *repeats* are the evidence chain: one snapshot digest standing in five
    receipts is what says the build, the activation and the experiment all ran
    against the same source. Rendered as opaque strings they are thirty-one
    unrelated fields; labelled by identity they are the graph.

    Order of first appearance, so the labels are stable for a given REE and a
    reader can cite ``D3`` and be understood.
    """
    order: list[str] = []
    counts: dict[str, int] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str) and node.startswith("sha256:"):
            if node not in counts:
                order.append(node)
                counts[node] = 0
            counts[node] += 1

    walk(ree)
    return {digest: (f"D{index + 1}", counts[digest]) for index, digest in enumerate(order)}


def _browse_value(value: Any, digests: dict[str, tuple[str, int]]) -> str:
    if isinstance(value, str) and value in digests:
        label, count = digests[value]
        repeated = f'<span class="times">&times;{count}</span>' if count > 1 else ""
        return (
            f'<button class="digest" data-digest="{escape(label)}" '
            f'title="{escape(value)}">{label}{repeated}'
            f'<span class="hex">{escape(value[7:19])}…</span></button>'
        )
    if isinstance(value, bool) or value is None:
        return f'<span class="lit">{json.dumps(value)}</span>'
    if isinstance(value, int | float):
        return f'<span class="num">{value}</span>'
    # Declared-and-empty is a different fact from absent, and both are common
    # here: an unset ``website`` is a string nobody filled in, not a missing
    # field. Rendering it as nothing at all left a row with a blank value.
    if value == "":
        return '<span class="lit">""</span>'
    return escape(str(value))


# A subtree bigger than this opens closed. The hardware observation is the only
# thing in a normal REE that reaches it, and it is exactly the one a reader
# scrolls past — but it is also real evidence, so it is folded rather than cut.
_FOLD_ABOVE = 12


def _leaf_count(node: Any) -> int:
    if isinstance(node, dict):
        return sum(_leaf_count(value) for value in node.values() if value is not None)
    if isinstance(node, list):
        return sum(_leaf_count(item) for item in node)
    return 1


def _is_branch(value: Any) -> bool:
    """Whether a value needs a block of its own rather than a spot on the row."""
    if isinstance(value, dict):
        return bool(value)
    return isinstance(value, list) and any(isinstance(item, dict | list) for item in value)


def _browse_children(node: Any, digests: dict[str, tuple[str, int]]) -> str:
    """One block of an object's or array's members.

    A leaf sits beside its key; a branch goes *below* it. Laying branches out
    beside the key instead nested a fixed-width label column inside every level,
    and by the fourth the value column was narrow enough to wrap long strings
    one character to a line — a tall grey ribbon where the hardware observation
    should have been.
    """
    if isinstance(node, list):
        return "".join(
            f'<div class="item">{_browse_children(item, digests)}</div>'
            if _is_branch(item)
            else f'<div class="item">{_browse_value(item, digests)}</div>'
            for item in node
        )
    rows: list[str] = []
    for key, value in node.items():
        if value is None:
            continue
        label = escape(str(key))
        if not _is_branch(value):
            if isinstance(value, list):
                shown = " ".join(_browse_value(item, digests) for item in value) or '<span class="lit">[]</span>'
            else:
                shown = _browse_value(value, digests)
            rows.append(f'<div class="row"><span class="key">{label}</span><div class="value">{shown}</div></div>')
            continue
        size = _leaf_count(value)
        opened = "" if size > _FOLD_ABOVE else " open"
        rows.append(
            f'<details class="nest"{opened}><summary><span class="key">{label}</span>'
            f'<span class="size">{size} fields</span></summary>'
            f'<div class="obj">{_browse_children(value, digests)}</div></details>'
        )
    return "".join(rows)


def render_browser(frame: Frame) -> str:
    """The finished REE as a page, with its digests joined up.

    Sections follow the aggregate's own shape, and each audited step carries the
    verdict the audit gave it, so the evidence and the standing of that evidence
    are not in two different documents.
    """
    digests = digest_index(frame.ree)
    subject = frame.ree["subject"]

    def section(title: str, node: Any, verdicts: dict[str, str] | None = None) -> str:
        if verdicts is None:
            children = _browse_children(node, digests)
            return f'<section><h2>{escape(title)}</h2><div class="obj">{children}</div></section>'
        # Receipts alone are titled by their audit verdict, so the evidence and
        # its standing are one thing to read rather than two documents to join.
        rows = []
        for key, value in node.items():
            if value is None or (key == "experiments" and not value):
                continue
            standing = verdicts.get(_VERDICT_KEYS.get(key, key), "")
            badge = f'<span class="badge {standing}">{standing.replace("_", " ")}</span>' if standing else ""
            size = _leaf_count(value)
            opened = "" if size > _FOLD_ABOVE else " open"
            rows.append(
                f'<details class="nest"{opened}><summary><span class="key">{escape(key)}</span>{badge}'
                f'<span class="size">{size} fields</span></summary>'
                f'<div class="obj">{_browse_children(value, digests)}</div></details>'
            )
        return f'<section><h2>{escape(title)}</h2><div class="obj">{"".join(rows)}</div></section>'

    body = [
        section("definition", subject["definition"]),
        section("receipts", subject["receipts"], frame.verdicts),
        section("contents", subject["contents"]),
    ]
    if frame.ree.get("seal"):
        body.append(section("seal", frame.ree["seal"]))

    legend = "".join(
        f'<button class="digest" data-digest="{label}" title="{escape(digest)}">{label}'
        f"{f"<span class='times'>&times;{count}</span>" if count > 1 else ''}"
        f'<span class="hex">{escape(digest[7:19])}…</span></button>'
        for digest, (label, count) in digests.items()
    )
    return _BROWSE_PAGE.format(
        label=escape(frame.label),
        status=escape(frame.status),
        distinct=len(digests),
        occurrences=sum(count for _, count in digests.values()),
        legend=legend,
        sections="\n".join(body),
    )


# The audit names two steps differently from the receipt slot they judge.
_VERDICT_KEYS = {"build": "runtime", "hardware_observation": "hardware"}


_BROWSE_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>REE browser</title>
<style>
  :root {{
    --ground:#fbfcfd; --card:#ffffff; --ink:#16202a; --soft:#5a6b78;
    --line:#dde4ea; --accent:#2d6b8c; --mark:#f0b429; --declare:#0f766e;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --ground:#10161c; --card:#161e26; --ink:#dde5ec; --soft:#8b9aa7;
             --line:#26343f; --accent:#6ab3d8; --mark:#8a6a12; --declare:#4fb3a5; }}
  }}
  body {{ background:var(--ground); color:var(--ink); margin:0;
         font:13px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
         padding:2.5rem 1.5rem 4rem; }}
  .page {{ max-width:68rem; margin:0 auto; }}
  h1 {{ font-size:1.1rem; margin:0 0 .3rem; }}
  .lede {{ color:var(--soft); font-size:.82rem; margin:0 0 1.2rem; max-width:66ch; }}
  .rail {{ display:flex; flex-wrap:wrap; gap:.35rem; padding:.85rem;
          border:1px solid var(--line); border-radius:3px; background:var(--card);
          margin-bottom:2rem; }}
  section {{ margin-bottom:2rem; }}
  h2 {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.12em;
       color:var(--accent); margin:0 0 .5rem; }}
  .obj {{ border-left:1px solid var(--line); padding-left:.85rem; }}
  .item {{ padding:.25rem 0; border-bottom:1px dotted var(--line); }}
  .item:last-child {{ border-bottom:none; }}
  .row {{ display:flex; gap:.85rem; align-items:baseline; padding:.09rem 0; }}
  /* Capped as a fraction as well as an absolute, so nesting cannot squeeze the
     value column into a one-character-per-line ribbon. */
  .key {{ color:var(--soft); min-width:min(15rem, 34%); flex-shrink:0; }}
  .value {{ flex:1; min-width:0; word-break:break-word; }}
  details.nest {{ margin:.1rem 0; }}
  details.nest > summary {{ cursor:pointer; display:flex; gap:.6rem;
                           align-items:baseline; padding:.09rem 0; }}
  details.nest > summary::marker {{ color:var(--soft); }}
  details.nest > .obj {{ margin-left:.3rem; }}
  .size {{ color:var(--soft); font-size:.68rem; }}
  .lit {{ color:var(--soft); }}
  .num {{ color:var(--declare); }}
  .badge {{ font-size:.6rem; text-transform:uppercase; letter-spacing:.08em;
           margin-left:.5rem; padding:.05em .4em; border-radius:2px;
           border:1px solid currentColor; }}
  .badge.current {{ color:var(--accent); }}
  .badge.stale {{ color:#a86a1b; }}
  .badge.missing, .badge.not_applicable {{ color:var(--soft); }}
  .digest {{ font:inherit; font-size:.78rem; cursor:pointer; color:var(--ink);
            background:var(--card); border:1px solid var(--line); border-radius:2px;
            padding:.05em .4em; display:inline-flex; gap:.35rem; align-items:baseline; }}
  .digest .hex {{ color:var(--soft); }}
  .digest .times {{ color:var(--declare); font-size:.7rem; }}
  .digest.on {{ background:var(--mark); border-color:var(--mark); color:#16202a; }}
  .digest.on .hex, .digest.on .times {{ color:#3b2f05; }}
</style>
<div class="page">
  <h1>REE browser <span class="lit">— {label} ({status})</span></h1>
  <p class="lede">
    {distinct} distinct digests across {occurrences} places. A digest that appears more than once
    is the evidence chain: click any one to light up every field holding the same value.
  </p>
  <div class="rail">{legend}</div>
{sections}
</div>
<script>
  let active = null;
  document.addEventListener("click", (event) => {{
    const chip = event.target.closest(".digest");
    const next = chip && chip.dataset.digest !== active ? chip.dataset.digest : null;
    active = next;
    for (const node of document.querySelectorAll(".digest")) {{
      node.classList.toggle("on", next !== null && node.dataset.digest === next);
    }}
  }});
</script>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-f", "--format", choices=("matrix", "timeline", "browse"), default="matrix")
    parser.add_argument("--frames", type=Path, default=CAPTURE, help="capture to render")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = parser.parse_args()

    if not args.frames.is_file():
        raise SystemExit(
            f"no capture at {args.frames} — run the api integration tier first (make api-integration-tests)"
        )
    frames = load_frames(args.frames)
    if args.format == "matrix":
        rendered = render_svg(frames, build_rows(frames))
    elif args.format == "timeline":
        rendered = render_timeline(frames, diff_frames(frames))
    else:
        # The last frame, because a browser is for the finished article: the
        # timeline is where the intermediate states are already answered for.
        rendered = render_browser(frames[-1])
    if args.output is None:
        print(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
