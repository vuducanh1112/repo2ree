"""Build output documents without reading templates or writing files."""

from collections import Counter

from repo2ree_history.core.evidence import AssemblyResult, Diagnostic
from repo2ree_history.core.sequence import render_sequence


def render_outputs(result: AssemblyResult) -> dict[str, str]:
    files = {"assembly.json": result.model_dump_json(indent=2) + "\n"}
    diagrams = []
    render_issues = []
    report = [
        "# Evidence report",
        "",
        f"Recording root: `{result.recording_root}`",
        "",
        f"Executions: {len(result.executions)}; unassigned observations: {len(result.unassigned)}.",
        "",
        "Artifact URIs resolve against the recording root. Assembly IDs and display order "
        "are not runtime identities or producer order.",
        "",
        "## Diagnostics",
        "",
    ]
    for (severity, code), count in sorted(Counter((d.severity, d.code) for d in result.diagnostics).items()):
        report.append(f"- {severity}: {code}: {count}")
    report.extend(["", "| Severity | Code | REE / execution | Detail |", "| --- | --- | --- | --- |"])
    for issue in result.diagnostics:
        scope = issue.ree_id or issue.execution_id or "recording"
        detail = issue.detail.replace("|", "&#124;").replace("\n", " ").replace("<", "&lt;")
        report.append(f"| {issue.severity} | {issue.code} | {scope} | {detail} |")
    for history in result.ree_histories:
        report.extend(
            [
                "",
                f"## REE {history.ree_id}",
                f"{len(history.event_ids)} observations across {len(history.execution_ids)} workbench lifecycles.",
            ]
        )
    report.extend(["", "## Source index", "", "| Artifact | URI |", "| --- | --- |"])
    report.extend(f"| {a.artifact_id} | `{a.uri}` |" for a in result.artifacts)
    for execution in result.executions:
        files[execution.execution_id + ".json"] = execution.model_dump_json(indent=2) + "\n"
        try:
            diagrams.append("```mermaid\n" + render_sequence(execution) + "```\n")
        except ValueError as exc:
            render_issues.append(
                Diagnostic(
                    code="sequence_unavailable",
                    severity="invalid",
                    detail=str(exc),
                    execution_id=execution.execution_id,
                )
            )
            report.extend(["", f"Sequence unavailable for {execution.execution_id}: {exc}"])

        report.extend(
            [
                "",
                f"## {execution.execution_id}",
                "",
                f"{len(execution.events)} observations.",
                "",
                "| Event | Kind | Source locator |",
                "| --- | --- | --- |",
            ]
        )
        for event in execution.events:
            sources = "; ".join(
                ref.model_dump_json().replace("|", "&#124;").replace("<", "&lt;") for ref in event.source_refs
            )
            report.append(f"| {event.event_id} | {event.payload.kind} | `{sources}` |")
    report.extend(["", "## Unassigned evidence", ""])
    report.extend(
        f"- {item.reason}: `" + "; ".join(r.model_dump_json().replace("`", "&#96;") for r in item.source_refs) + "`"
        for item in result.unassigned
    )
    report.extend(["", "Full diagnostics and references are retained in `assembly.json`.", ""])
    if render_issues:
        result = result.model_copy(update={"diagnostics": (*result.diagnostics, *render_issues)})
        files["assembly.json"] = result.model_dump_json(indent=2) + "\n"
    files["evidence-report.md"] = "\n".join(report)
    files["sequence.md"] = "\n".join(diagrams) or "No lifecycle could be assigned. See evidence-report.md.\n"
    return files
