"""Visualize the behaviour of an e2e run's tests, or of one dossier, from what was assessed.

Drawing decides nothing: it reads what ``repo2ree_testbed assess`` recorded, draws each test's
traces and provenance from its verification/ into traces/, and writes the pages to browse a run
by: one per test (its outcome, verdict, last failed command, artifacts, and screenshots) and one
for the run. A dossier collected from a live deployment (``collect-dossier``) has its traces drawn
under the assurance directory, beside its verification, by its name.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

from repo2ree_testbed.artifacts import domain_dir
from repo2ree_testbed.records import RunRecord, RunTest, read
from repo2ree_testbed.runs.assess import failed_command, is_run, run_of, target, tool
from repo2ree_testbed.runs.failed_command import FailedCommand

STYLE = """
:root { color-scheme: light dark; --fg: #1d2330; --muted: #5b6475; --line: #d9dee7; --bg: #fbfcfe;
  --pass: #1a7f45; --fail: #b42318; --warn: #a15c00; }
@media (prefers-color-scheme: dark) { :root { --fg: #e6e9ef; --muted: #9aa3b2; --line: #2e3442; --bg: #151922;
  --pass: #4cc38a; --fail: #f97066; --warn: #fdb022; } }
body { font: 15px/1.5 system-ui, sans-serif; color: var(--fg); background: var(--bg); margin: 0 auto;
  max-width: 1200px; padding: 24px 16px; }
h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 17px; margin: 28px 0 8px; }
.muted { color: var(--muted); } table { border-collapse: collapse; width: 100%; }
td, th { border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left; vertical-align: top; }
.passed { color: var(--pass); font-weight: 600; } .failed, .violated { color: var(--fail); font-weight: 600; }
.inconclusive, .missing, .xfailed, .skipped { color: var(--warn); font-weight: 600; }
.shots { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
figure { margin: 0; } figure img { width: 100%; border: 1px solid var(--line); border-radius: 6px; }
figcaption { font-size: 13px; color: var(--muted); } a { color: inherit; }
pre { font-size: 13px; white-space: pre-wrap; border: 1px solid var(--line); border-radius: 6px; padding: 8px; }
"""


def page(title: str, body: str) -> str:
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'><title>{html.escape(title)}</title>"
        f"<style>{STYLE}</style></head><body>{body}</body></html>\n"
    )


def links(directory: Path, pattern: str) -> list[Path]:
    return sorted(path.relative_to(directory) for path in directory.glob(pattern))


def write_test_index(directory: Path, test: RunTest, failed: FailedCommand | None = None) -> None:
    rows = [
        ("Test outcome", f"<span class='{test.outcome}'>{test.outcome}</span> (exit {test.exit_code})"),
        ("Reason", html.escape(test.reason) or "<span class='muted'>none</span>"),
        *(
            [("Last failed command", f"<code>{html.escape(test.last_failed_command)}</code>")]
            if test.last_failed_command
            else []
        ),
        ("Behaviour", f"<span class='{test.behaviour}'>{test.behaviour}</span>"),
        ("Duration", f"{test.duration:.0f} s, stack start to teardown"),
        (
            "Phases",
            html.escape(", ".join(f"{name} {seconds:.1f} s" for name, seconds in test.phases.items()))
            or "<span class='muted'>not recorded</span>",
        ),
        ("REEs", ", ".join(html.escape(ree) for ree in test.rees) or "none recorded"),
    ]
    body = [f"<h1>{html.escape(test.name)}</h1>", "<table>"]
    body += [f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in rows]
    body.append("</table>")
    if failed is not None:
        body.append("<h2>Last failed command</h2>")
        body.append(
            "<p class='muted'>What execution recorded, beside the test outcome; the behaviour verdict judges the"
            " dossier against the spec and does not rest on it.</p>"
        )
        body.append(f"<p><code>{html.escape(failed.argv)}</code> exited {html.escape(str(failed.exit_code))}</p>")
        body.append(f"<pre>{html.escape(failed.stderr_tail)}</pre>")

    pages = [("Assurance report", path) for path in links(directory, "verification/assurance.html")]
    pages += [(f"Behaviour trace {path.stem}", path) for path in links(directory, "traces/*.html")]
    pages += [(f"Provenance {path.name.split('.')[0]}", path) for path in links(directory, "traces/*.provenance.txt")]
    pages += [(f"Log {path.name}", path) for path in links(directory, "logs/*.log")]
    pages += [(f"Kept REE {path.name}", path) for path in links(directory, "artifacts/**/*.zip")]
    pages += [("Dossier manifest", path) for path in links(directory, "dossier/manifest.json")]
    body.append("<h2>Artifacts</h2><ul>")
    body += [f"<li><a href='{html.escape(str(path))}'>{html.escape(label)}</a></li>" for label, path in pages]
    body.append("</ul>")

    shots = sorted(
        links(directory, "artifacts/**/*.png"),
        key=lambda shot: (shot.parent, shot.stem.removesuffix("-after").removesuffix("-before"), "after" in shot.stem),
    )
    if shots:
        body.append("<h2>Screenshots</h2><div class='shots'>")
        body += [
            f"<figure><a href='{html.escape(str(shot))}'><img loading='lazy' src='{html.escape(str(shot))}' "
            f"alt='{html.escape(shot.stem)}'></a><figcaption>{html.escape(shot.stem)}</figcaption></figure>"
            for shot in shots
        ]
        body.append("</div>")
    (directory / "index.html").write_text(page(test.name, "".join(body)))


def write_run_index(root: Path, run: RunRecord) -> None:
    body = [
        f"<h1>{html.escape(run.tier)} run</h1>",
        (
            f"<p class='muted'>{html.escape(root.name)} · build {html.escape(run.build_revision or '?')} · "
            f"each test on a fresh stack</p>"
        ),
        "<table><tr><th>Test</th><th>Outcome</th><th>Behaviour</th><th>Duration</th><th>REEs</th></tr>",
    ]
    body += [
        f"<tr><td><a href='{html.escape(test.directory)}/index.html'>{html.escape(test.name)}</a></td>"
        f"<td><span class='{test.outcome}'>{test.outcome}</span>"
        + (
            f"<br><span class='muted'>last failed command: {html.escape(test.last_failed_command)}</span>"
            if test.last_failed_command
            else ""
        )
        + f"</td><td class='{test.behaviour}'>{test.behaviour}</td>"
        f"<td>{test.duration:.0f} s</td><td>{len(test.rees)}</td></tr>"
        for test in run.tests
    ]
    body.append("</table>")
    (root / "index.html").write_text(page(f"{run.tier} run", "".join(body)))


def draw(verification: Path, traces: Path, logs: Path) -> bool:
    """Draw a verification's traces and provenance into ``traces``; False when there is nothing to draw from."""
    if not (verification / "verification.json").is_file():
        return False
    trace = ("repo2ree_assurance_traceview", "trace", str(verification), "-o", str(traces), "--provenance")
    return tool(logs / "traceview.log", *trace) == 0


def visualize_test(directory: Path, test: RunTest) -> None:
    drawn = bool(test.rees) and draw(directory / "verification", directory / "traces", directory / "logs")
    write_test_index(directory, test, failed_command(directory, test))
    shown = "drawn" if drawn else "no REE" if not test.rees else "not drawn"
    print(f"   {shown:<9} {test.name}")


def visualize_run(root: Path) -> None:
    run = read(RunRecord, root / "run.json")
    if run is None:
        raise ValueError(f"{root}: no run record (run.json) to visualize")
    for test in run.tests:
        visualize_test(root / test.directory, test)
    write_run_index(root, run)
    print(f">> visualized: {root / 'index.html'}")


def visualize_dossier(dossier: Path) -> None:
    """Visualize one dossier: as its test, if a run's test left it, else under the assurance directory."""
    found = run_of(dossier)
    if found is not None:
        root, run = found
        name = str(dossier.parent.relative_to(root))
        [test] = [test for test in run.tests if test.directory == name]
        visualize_test(dossier.parent, test)
        write_run_index(root, run)
        print(f">> visualized: {dossier.parent / 'index.html'}")
        return
    reports = domain_dir("assurance")
    traces = reports / "traces" / dossier.name
    if not draw(reports / "verification" / dossier.name, traces, reports / "logs" / dossier.name):
        raise ValueError(f"{dossier}: no verification to draw from; assess it first: just assess-behaviour {dossier}")
    print(f">> visualized: {traces}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    # A string, not a path: a recipe passes "" for "the newest", and Path("") would be the working directory.
    parser.add_argument("path", nargs="?", default="", help="a run or a dossier (default: the newest run)")
    args = parser.parse_args()
    try:
        chosen = target(args.path)
        if is_run(chosen):
            visualize_run(chosen)
        else:
            visualize_dossier(chosen)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
