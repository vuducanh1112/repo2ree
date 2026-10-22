"""Judge and draw every test of an e2e run, and write its pages; never changes a test's outcome."""

from __future__ import annotations

import argparse
import html
import subprocess
import sys
from pathlib import Path

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.records import Behaviour, RunRecord, RunTest, read, write

VERDICTS: dict[int, Behaviour] = {0: "passed", 1: "violated", 2: "inconclusive"}

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
"""


def page(title: str, body: str) -> str:
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'><title>{html.escape(title)}</title>"
        f"<style>{STYLE}</style></head><body>{body}</body></html>\n"
    )


def tool(log: Path, *args: str) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("wb") as output:
        command = [sys.executable, "-m", *args]
        return subprocess.run(command, cwd=ROOT, check=False, stdout=output, stderr=subprocess.STDOUT).returncode


def inspect_test(directory: Path, test: RunTest) -> RunTest:
    recording = directory / "recording"
    verification = directory / "verification"
    logs = directory / "logs"
    verdict: Behaviour = "missing"
    if (recording / "manifest.json").is_file():
        check = ("repo2ree_conformance", "check", "--recording", str(recording), "-o", str(verification))
        verdict = VERDICTS.get(tool(logs / "conformance.log", *check), "error")
    if (verification / "verification.json").is_file() and test.rees:
        draw = ("repo2ree_traceview", str(verification), "-o", str(directory / "traces"), "--provenance")
        tool(logs / "traceview.log", *draw)
    inspected = test.judged(verdict)
    write_test_index(directory, inspected)
    return inspected


def links(directory: Path, pattern: str) -> list[Path]:
    return sorted(path.relative_to(directory) for path in directory.glob(pattern))


def write_test_index(directory: Path, test: RunTest) -> None:
    rows = [
        ("Test outcome", f"<span class='{test.outcome}'>{test.outcome}</span> (exit {test.exit_code})"),
        ("Reason", html.escape(test.reason) or "<span class='muted'>none</span>"),
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

    pages = [("Conformance report", path) for path in links(directory, "verification/conformance.html")]
    pages += [(f"Operation trace {path.stem}", path) for path in links(directory, "traces/*.html")]
    pages += [(f"Provenance {path.name.split('.')[0]}", path) for path in links(directory, "traces/*.provenance.txt")]
    pages += [(f"Log {path.name}", path) for path in links(directory, "logs/*.log")]
    pages += [(f"Kept REE {path.name}", path) for path in links(directory, "artifacts/**/*.zip")]
    pages += [("Recording manifest", path) for path in links(directory, "recording/manifest.json")]
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
        f"<p class='muted'>{html.escape(root.name)} · build {html.escape(run.build_revision or '?')} · "
        f"each test on a fresh stack</p>",
        "<table><tr><th>Test</th><th>Outcome</th><th>Behaviour</th><th>Duration</th><th>REEs</th></tr>",
    ]
    body += [
        f"<tr><td><a href='{html.escape(test.directory)}/index.html'>{html.escape(test.name)}</a></td>"
        f"<td class='{test.outcome}'>{test.outcome}</td><td class='{test.behaviour}'>{test.behaviour}</td>"
        f"<td>{test.duration:.0f} s</td><td>{len(test.rees)}</td></tr>"
        for test in run.tests
    ]
    body.append("</table>")
    (root / "index.html").write_text(page(f"{run.tier} run", "".join(body)))


def inspect_run(root: Path) -> RunRecord:
    run = read(RunRecord, root / "run.json")
    if run is None:
        raise ValueError(f"{root}: no run record (run.json) to inspect")
    tests = []
    for test in run.tests:
        inspected = inspect_test(root / test.directory, test)
        tests.append(inspected)
        print(f"   {inspected.outcome:<7} behaviour {inspected.behaviour or '':<12} {test.name}")
    inspected_run = run.with_tests(tuple(tests))
    write_run_index(root, inspected_run)
    write(root / "run.json", inspected_run)
    print(f">> inspection: {root / 'index.html'}")
    return inspected_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="the run directory an e2e run wrote")
    try:
        inspect_run(parser.parse_args().run)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
