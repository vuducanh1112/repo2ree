import type { DecisionDag, DecisionTrace, InferenceReport } from "@shell/infra/api/apiTypes";
import type { ScriptGeneration } from "./generation";
import { dagForTrace, findResult, type InferenceResult, traceForResult } from "./reportSelectors";

// Every target a page can generate a script for. They differ only in how the
// engine infers them — the reduction from report to loadable script is
// identical, so it lives here once. Build used to have its own copy of this
// file and fell behind when the build DAG started emitting blocking warnings.
export type ScriptTargetKind = "build" | "activation_run" | "experiment_run";

function matches(kind: ScriptTargetKind, experimentName?: string) {
  return (result: InferenceResult): boolean => {
    if (result.target.kind !== kind) return false;
    if (kind === "experiment_run") return result.target.experiment_name === experimentName;
    return true;
  };
}

/**
 * Reduce an inference report to what a script page needs: the target's first
 * viable candidate as a single self-contained script to load into the editor,
 * or a not-inferred outcome. Pure so the choice is unit-testable without the API.
 *
 * When a target is a decision (several viable strategies), the first candidate
 * is chosen as the one to load; the caller surfaces the alternative count so the
 * author knows others exist. Blocking warnings ride along either way — they are
 * how the engine explains what the author must fix.
 */
export function selectCandidate(
  report: InferenceReport,
  kind: ScriptTargetKind,
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

/**
 * The target's decision trace — the executed DAG walk that explains why
 * inference did (or did not) produce a candidate. `null` only if the report has
 * no such target.
 */
export function selectTrace(
  report: InferenceReport,
  kind: ScriptTargetKind,
  experimentName?: string,
): DecisionTrace | null {
  return traceForResult(report, matches(kind, experimentName));
}

/** The static DAG (the full graph) the trace overlays onto, matched by key. */
export function selectDag(
  report: InferenceReport,
  kind: ScriptTargetKind,
  experimentName?: string,
): DecisionDag | null {
  return dagForTrace(report, selectTrace(report, kind, experimentName));
}
