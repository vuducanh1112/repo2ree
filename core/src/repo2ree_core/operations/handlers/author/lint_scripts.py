"""Handle read-only lint of scripts present in the overlay."""

from __future__ import annotations

from typing import Any

from repo2ree_core.author_recipes.lint import ScriptDeclarations, lint_script
from repo2ree_core.author_recipes.targets import ScriptTargetSelector, resolve_target
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import LintScriptsArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_lint_scripts(
    args: LintScriptsArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if not args.targets:
        return ActionResult.failed("validation", "no lint targets requested")

    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)
    ree = store.read_ree() if store.manifest_exists() else None
    declarations = ScriptDeclarations.from_definition(ree.subject.definition if ree else None)

    reports: list[dict[str, Any]] = []
    missing: list[str] = []
    try:
        for selector in args.targets:
            target = resolve_target(ScriptTargetSelector(kind=selector.kind, experiment_name=selector.experiment_name))
            script = layout.overlay_file(target.path)
            if not script.is_file():
                missing.append(target.path)
                continue
            report = lint_script(target, script.read_text(), declarations=declarations)
            reports.append(report.model_dump())
    except ValueError as exc:
        log("system", "error", f"invalid lint target: {exc}")
        return ActionResult.failed("validation", f"invalid lint target: {exc}")
    except Exception as exc:
        log("system", "error", f"lint_scripts failed: {exc}")
        return failed_from_exception(exc, f"lint_scripts failed: {exc}")

    if is_canceled():
        log("system", "warn", "lint_scripts canceled")
        return ActionResult(status="canceled")

    findings = sum(len(report["findings"]) for report in reports)
    log("system", "info", f"linted {len(reports)} script(s); {findings} finding(s)")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs={"reports": reports, "missing_scripts": missing},
    )
