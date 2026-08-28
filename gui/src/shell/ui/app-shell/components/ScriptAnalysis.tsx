import {
  analysisState,
  findingTone,
  type LintFinding,
  type LintTarget,
} from "@shell/data/scriptLint/findings";
import { useSavedScriptLint, useScriptDraftLint } from "@shell/data/scriptLint/queries";
import { useDebouncedValue } from "@shell/ui/shared/hooks/useDebouncedValue";
import { useEffect } from "react";
import styles from "./ScriptAnalysis.module.css";
import { usePublishScriptDiagnostics } from "./scriptDiagnostics";

const SETTLE_MS = 400;

const NO_FINDINGS: readonly LintFinding[] = [];

interface ScriptAnalysisProps {
  target: LintTarget;
  source: string;
  dirty: boolean;
  runtimePath: string | null;
  onFocusLine?: (line: number) => void;
  disabled?: boolean;
}

/** Show contract checks for a draft or the full report for saved source. */
export function ScriptAnalysis({
  target,
  source,
  dirty,
  runtimePath,
  onFocusLine,
  disabled = false,
}: ScriptAnalysisProps) {
  const settled = useDebouncedValue(source, SETTLE_MS);
  const draft = useScriptDraftLint(target, settled, runtimePath, {
    enabled: !disabled && dirty,
  });
  const saved = useSavedScriptLint(target, source, { enabled: !disabled && !dirty });

  const active = dirty ? draft : saved;
  const state = analysisState({
    report: active.data ?? undefined,
    isFetching: active.isFetching,
    error: active.error,
    enabled: !disabled,
  });

  // The same findings the list below renders, sent back up to the editor to be
  // drawn on the lines they name. `state.findings` is the report's own tuple, so
  // this publishes once per report rather than once per render.
  const findings = state.kind === "findings" ? state.findings : NO_FINDINGS;
  const publish = usePublishScriptDiagnostics();
  useEffect(() => publish(findings), [findings, publish]);

  if (state.kind === "idle") return null;

  const scope = dirty ? "as you type" : "on the saved script";

  return (
    <div className={styles.panel}>
      <div className={styles.status} role="status">
        {state.kind === "checking" && <span>Checking…</span>}
        {state.kind === "error" && <span>Checks unavailable: {state.message}</span>}
        {state.kind === "clean" && <span className={styles.headline}>No findings</span>}
        {state.kind === "findings" && (
          <span className={styles.headline}>{state.summary.headline}</span>
        )}
        {state.kind !== "checking" && state.kind !== "error" && (
          <span className={styles.scope}>{scope}</span>
        )}
      </div>

      {state.kind === "findings" && (
        <ul className={styles.list}>
          {state.findings.map((finding) => (
            <li key={`${finding.code}:${finding.line ?? 0}:${finding.detail ?? ""}`}>
              <button
                type="button"
                className={styles.finding}
                data-tone={findingTone(finding.severity)}
                onClick={() => finding.line && onFocusLine?.(finding.line)}
              >
                <span className={styles.line}>{finding.line ? `L${finding.line}` : "—"}</span>
                <span className={styles.code}>{finding.code}</span>
                <span>{finding.message}</span>
                {finding.detail && <span className={styles.detail}>{finding.detail}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {(state.kind === "clean" || state.kind === "findings") && state.unrun.length > 0 && (
        <p className={styles.unrun}>
          {state.unrun.map((tier) => `${tier.tier}: ${tier.detail ?? "did not run"}`).join(" · ")}
        </p>
      )}
    </div>
  );
}
