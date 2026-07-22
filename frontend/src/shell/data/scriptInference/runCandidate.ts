import type { DecisionDag, DecisionTrace, InferenceReport } from "@shell/infra/api/apiTypes";
import type { ScriptGeneration } from "./generation";
import { dagForTrace, findResult, type InferenceResult, traceForResult } from "./reportSelectors";

// A run-target kind the build-runtime / experiment pages can generate a script
// for. Build has its own selector (buildCandidate.ts); these cover the runtime
// load/run scaffolds that share one shape.
export type RunTargetKind = "activation_run" | "experiment_run";

function matches(kind: RunTargetKind, experimentName?: string) {
  return (result: InferenceResult): boolean => {
    if (result.target.kind !== kind) return false;
    if (kind === "experiment_run") return result.target.experiment_name === experimentName;
    return true;
  };
}

/**
 * Reduce an inference report to the run target's first viable candidate as a
 * single self-contained scaffold, or a not-inferred outcome. Pure so the choice
 * is unit-testable without the API.
 */
export function selectRunCandidate(
  report: InferenceReport,
  kind: RunTargetKind,
  experimentName?: string,
): ScriptGeneration {
  const result = findResult(report, matches(kind, experimentName));
  const candidates = result?.candidates ?? [];
  const blockingMessages = (result?.warnings ?? []).filter((w) => w.blocking).map((w) => w.message);
  const candidate = candidates.find(
    (entry) => typeof entry.body === "string" && entry.body.length > 0,
  );
  if (!result || !candidate || typeof candidate.body !== "string") {
    return { status: "not_inferred", blockingMessages };
  }
  return {
    status: "generated",
    script: {
      body: candidate.body,
      ruleId: candidate.inference_rule,
      application: candidate.application,
      alternativeCount: candidates.length,
      blockingMessages,
    },
  };
}

/** The run target's decision trace, or `null` if the report has no such target. */
export function selectRunTrace(
  report: InferenceReport,
  kind: RunTargetKind,
  experimentName?: string,
): DecisionTrace | null {
  return traceForResult(report, matches(kind, experimentName));
}

/** The static DAG the run trace overlays onto, matched by key. */
export function selectRunDag(
  report: InferenceReport,
  kind: RunTargetKind,
  experimentName?: string,
): DecisionDag | null {
  return dagForTrace(report, selectRunTrace(report, kind, experimentName));
}
