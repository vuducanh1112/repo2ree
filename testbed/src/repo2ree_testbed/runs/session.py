"""Draw a CLI test's session: each ``ree`` command it ran, with what it read and answered, and the REE as each left it.

The commands are the client's session (``cli_session``); the REE is the history the dossier keeps of it. Every
attempt core runs is a commit whose message records its command, its run and its result, so each command is matched
to the commits its run made, and each commit shows its document (``ree.json``, or a review's ``review.json``) and
file tree beside the ones before it. A command that made no commit, a read, changed nothing.

    python -m repo2ree_testbed session <test directory> -o <report directory>
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from repo2ree_testbed.cli_session import SESSION, CliCommand, read_session

# Where an REE's history and a review's keep their document.
DOCUMENTS = ("ree.json", "review.json")
HISTORY = "refs/heads/ree-history"
# A value shown in a change is cut at this many characters.
VALUE_WIDTH = 120


@dataclass(frozen=True)
class File:
    blob: str
    size: int


@dataclass(frozen=True)
class Commit:
    """One commit of an REE's history: the attempt it records, and the REE as it left it."""

    ree: str
    scope: str
    commit: str
    operation: str
    run_id: str | None
    outcome: str | None
    files: dict[str, File]
    document: str | None
    document_path: str | None


@dataclass(frozen=True)
class Change:
    """A commit beside the one before it in its history."""

    commit: Commit
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    fields: tuple[tuple[str, str, str], ...]

    @property
    def unchanged(self) -> bool:
        return not (self.added or self.removed or self.changed)


@dataclass
class Step:
    """One command, and the commits its run made."""

    command: CliCommand
    changes: list[Change] = field(default_factory=list)


# ================================================
# Reading the histories
# ================================================


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "--git-dir", str(repository / ".git"), *args], check=True, capture_output=True, text=True
    ).stdout


def histories(dossier: Path) -> Iterator[tuple[str, str, Path]]:
    """Every history the dossier keeps of an REE: its own, and each review's, with the scope it sits at."""
    for root in sorted((dossier / "rees").glob("*/ree")):
        if (root / ".git").is_dir():
            yield root.parent.name, "", root
        for review in sorted((root / "reviews").glob("*")):
            if (review / ".git").is_dir():
                yield root.parent.name, f"reviews/{review.name}/", review


def commits(ree: str, scope: str, repository: Path) -> list[Commit]:
    listed = _git(repository, "log", "--reverse", "--format=%H%x1f%B%x1e", HISTORY)
    found = []
    for entry in listed.split("\x1e"):
        if not entry.strip():
            continue
        commit, _, message = entry.strip().partition("\x1f")
        subject, _, body = message.partition("\n\n")
        metadata = _metadata(body)
        record = metadata.record or _Record()
        files = _files(repository, commit)
        path = next((name for name in DOCUMENTS if name in files), None)
        found.append(
            Commit(
                ree=ree,
                scope=scope,
                commit=commit,
                operation=record.command.operation or subject.strip(),
                run_id=metadata.run_id or record.run_id,
                outcome=metadata.outcome or record.operation_status,
                files=files,
                document=_git(repository, "show", f"{commit}:{path}") if path else None,
                document_path=path,
            )
        )
    return found


class _Read(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Command(_Read):
    operation: str = ""


class _Record(_Read):
    run_id: str | None = None
    operation_status: str | None = None
    command: _Command = _Command()


class _Metadata(_Read):
    """What a commit's message records of the attempt it captured: its run, how it ended, and its record."""

    run_id: str | None = None
    outcome: str | None = None
    record: _Record | None = None


def _metadata(body: str) -> _Metadata:
    try:
        return _Metadata.model_validate_json(body)
    except ValidationError:
        return _Metadata()


def _files(repository: Path, commit: str) -> dict[str, File]:
    files = {}
    for line in _git(repository, "ls-tree", "-r", "-l", commit).splitlines():
        meta, _, path = line.partition("\t")
        _mode, _kind, blob, size = meta.split()
        files[path] = File(blob, int(size) if size.isdigit() else 0)
    return files


def changes(found: list[Commit]) -> list[Change]:
    """Each commit beside the one before it in the same history."""
    result = []
    before: Commit | None = None
    for commit in found:
        old = before.files if before else {}
        new = commit.files
        result.append(
            Change(
                commit=commit,
                added=tuple(sorted(set(new) - set(old))),
                removed=tuple(sorted(set(old) - set(new))),
                changed=tuple(sorted(path for path in set(old) & set(new) if old[path].blob != new[path].blob)),
                fields=tuple(_fields(before.document if before else None, commit.document)),
            )
        )
        before = commit
    return result


def _fields(before: str | None, after: str | None) -> Iterator[tuple[str, str, str]]:
    """Every value of the document that changed, by its dotted path, with what it was and what it became."""
    old = dict(_flatten(_parsed(before)))
    new = dict(_flatten(_parsed(after)))
    for path in sorted(set(old) | set(new)):
        if old.get(path) != new.get(path):
            yield path, old.get(path, "—"), new.get(path, "—")


def _parsed(document: str | None) -> Any:
    try:
        return json.loads(document) if document else None
    except ValueError:
        return None


def _flatten(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, Mapping):
        if not value and path:
            yield path, "{}"
        for key, item in value.items():
            yield from _flatten(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        if not value and path:
            yield path, "[]"
        for index, item in enumerate(value):
            yield from _flatten(item, f"{path}[{index}]")
    else:
        text = json.dumps(value)
        yield path, text if len(text) <= VALUE_WIDTH else text[: VALUE_WIDTH - 1] + "…"


def steps(session: tuple[CliCommand, ...], dossier: Path) -> tuple[list[Step], list[Change]]:
    """Each command with the commits its run made; and the commits no command of the session made."""
    found = [Step(command) for command in session]
    by_run = {step.command.run_id: step for step in found if step.command.run_id}
    unmatched: list[Change] = []
    for ree, scope, repository in histories(dossier):
        held = changes(commits(ree, scope, repository))
        pending: list[Change] = []
        for change in held:
            run = change.commit.run_id
            step = by_run.get(run) or by_run.get(run.rsplit(".", 1)[0]) if run else None
            if step is None and change.commit.operation == "initialize_ree":
                step = next((s for s in found if s.command.ree == ree and s.command.words[:1] == ("init",)), None)
            if step is None:
                pending.append(change)
                continue
            # A commit no run made (a baseline a review takes first) is shown with the command that came next.
            step.changes += [*pending, change]
            pending = []
        unmatched += pending
    return found, unmatched


# ================================================
# Drawing
# ================================================

STYLE = """
body{font:14px/1.5 system-ui,sans-serif;margin:0;color:#0f172a;background:#f8fafc}
main{max-width:1100px;margin:0 auto;padding:24px}
h1{font-size:20px;margin:0 0 4px}
.muted{color:#64748b}
.step{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;margin:12px 0}
.step.read{background:#f8fafc;padding:6px 16px}
.cmd{font:13px ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-all}
.badge{display:inline-block;font-size:11px;padding:1px 8px;border-radius:999px;margin-left:6px}
.succeeded{background:#dcfce7;color:#166534}.failed{background:#fee2e2;color:#991b1b}
.canceled,.other{background:#fef3c7;color:#92400e}
.ree{font-size:11px;color:#475569;background:#e2e8f0;border-radius:4px;padding:1px 6px}
details{margin:6px 0}summary{cursor:pointer;color:#475569;font-size:13px}
pre{background:#f1f5f9;border-radius:6px;padding:8px;overflow:auto;font-size:12px;max-height:420px}
table{border-collapse:collapse;font-size:12px;margin:4px 0;width:100%}
td{border-top:1px solid #e2e8f0;padding:2px 8px;vertical-align:top}
td.path{font-family:ui-monospace,Menlo,monospace;word-break:break-all}
.add{color:#166534}.del{color:#991b1b}.mod{color:#92400e}
.attempt{border-left:3px solid #94a3b8;padding-left:10px;margin:8px 0}
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _badge(status: str) -> str:
    tone = status if status in ("succeeded", "failed", "canceled") else "other"
    return f'<span class="badge {tone}">{_esc(status)}</span>'


def _tree(files: Mapping[str, File]) -> str:
    return "\n".join(f"{file.size:>10}  {path}" for path, file in sorted(files.items()))


def _change(change: Change) -> str:
    commit = change.commit
    where = f"{commit.ree}/{commit.scope}" if commit.scope else commit.ree
    head = (
        f"<div><b>{_esc(commit.operation)}</b> {_badge(commit.outcome or 'recorded')} "
        f'<span class="muted">commit <code>{commit.commit[:10]}</code> in {_esc(where)}</span></div>'
    )
    if change.unchanged:
        return f'<div class="attempt">{head}<div class="muted">the REE did not change</div></div>'
    rows = [
        *(f'<tr><td class="add">+</td><td class="path">{_esc(p)}</td></tr>' for p in change.added),
        *(f'<tr><td class="del">&minus;</td><td class="path">{_esc(p)}</td></tr>' for p in change.removed),
        *(f'<tr><td class="mod">~</td><td class="path">{_esc(p)}</td></tr>' for p in change.changed),
    ]
    files = f"<table>{''.join(rows)}</table>"
    fields = ""
    if change.fields:
        shown = "".join(
            f'<tr><td class="path">{_esc(path)}</td><td class="del">{_esc(before)}</td>'
            f'<td class="add">{_esc(after)}</td></tr>'
            for path, before, after in change.fields
        )
        fields = (
            f"<details><summary>{len(change.fields)} changed in {_esc(commit.document_path)}</summary>"
            f"<table>{shown}</table></details>"
        )
    document = (
        f"<details><summary>{_esc(commit.document_path)} after it</summary><pre>{_esc(_pretty(commit.document))}</pre>"
        "</details>"
        if commit.document
        else ""
    )
    tree = (
        f"<details><summary>the file tree after it ({len(commit.files)} files)</summary>"
        f"<pre>{_esc(_tree(commit.files))}</pre></details>"
    )
    return f'<div class="attempt">{head}{files}{fields}{document}{tree}</div>'


def _pretty(document: str | None) -> str:
    parsed = _parsed(document)
    return json.dumps(parsed, indent=2) if parsed is not None else (document or "")


def _step(number: int, step: Step) -> str:
    command = step.command
    typed = "ree " + " ".join(command.words)
    status = command.status
    if not step.changes and status == "succeeded":
        return (
            f'<div class="step read"><span class="muted">{number}</span> <span class="cmd">{_esc(typed)}</span> '
            f'<span class="ree">{_esc(command.ree)}</span> <span class="muted">read, changed nothing · '
            f"{command.duration:.1f} s</span></div>"
        )
    parts = [
        (
            f'<div class="step"><div><span class="muted">{number}</span> <span class="cmd">$ {_esc(typed)}</span>'
            f'{_badge(status)} <span class="ree">{_esc(command.ree)}</span> '
            f'<span class="muted">exit {command.exit} · {command.duration:.1f} s</span></div>'
        )
    ]
    if command.stdin is not None:
        parts.append(
            f"<details><summary>stdin, {command.stdin_bytes} bytes</summary><pre>{_esc(command.stdin)}</pre></details>"
        )
    if command.result is not None:
        failure = command.result.get("failure")
        if isinstance(failure, dict):
            parts.append(f'<div class="del">{_esc(failure.get("category"))}: {_esc(failure.get("message"))}</div>')
        outputs = command.result.get("outputs")
        if outputs:
            parts.append(
                f"<details><summary>outputs</summary><pre>{_esc(json.dumps(outputs, indent=2))}</pre></details>"
            )
        elif command.result_bytes > len(json.dumps(command.result)):
            parts.append(f'<div class="muted">outputs of {command.result_bytes} bytes, not kept</div>')
    elif command.stdout_bytes:
        parts.append(f'<div class="muted">printed {command.stdout_bytes} bytes</div>')
    if command.log:
        parts.append(
            f"<details><summary>log, {len(command.log)} lines</summary><pre>{_esc(chr(10).join(command.log))}</pre>"
            "</details>"
        )
    parts += [_change(change) for change in step.changes]
    parts.append("</div>")
    return "".join(parts)


def render(name: str, found: list[Step], unmatched: list[Change]) -> str:
    changed = sum(1 for step in found if any(not change.unchanged for change in step.changes))
    lede = (
        f"{len(found)} <code>ree</code> commands, {changed} of which changed an REE. Each command as the test ran it, "
        "what it read and answered, and the REE as it left it: the attempts its run recorded, the files they added "
        "(+), removed (&minus;) and changed (~), the document's changed values, and the document and file tree "
        "after it."
    )
    body = [f"<h1>CLI session</h1><p class='muted'>{_esc(name)}</p><p>{lede}</p>"]
    body += [_step(number, step) for number, step in enumerate(found, start=1)]
    if unmatched:
        body.append("<h2>Commits no command of the session made</h2>")
        body += [_change(change) for change in unmatched]
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>CLI session</title>"
        f"<style>{STYLE}</style></head><body><main>{''.join(body)}</main></body></html>"
    )


def draw(evidence: Path, output: Path, name: str) -> bool:
    """Draw the session a test left in ``evidence`` into ``output``; False when it left none."""
    session = read_session(evidence / "artifacts" / SESSION)
    if not session:
        return False
    found, unmatched = steps(session, evidence / "dossier")
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(render(name, found, unmatched), encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("evidence", type=Path, help="the test's directory in its run")
    parser.add_argument("-o", "--output", type=Path, required=True, help="where to write the session page")
    args = parser.parse_args()
    return 0 if draw(args.evidence, args.output, args.evidence.name) else 1


if __name__ == "__main__":
    raise SystemExit(main())
