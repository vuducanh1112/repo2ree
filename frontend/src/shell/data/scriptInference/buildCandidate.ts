import type { DecisionDag, DecisionTrace, InferenceReport } from "@shell/infra/api/apiTypes";
import type { ScriptGeneration } from "./generation";
import { dagForTrace, findResult, traceForResult } from "./reportSelectors";

const isBuild = (result: { target: { kind: string } }) => result.target.kind === "build";

/**
 * Reduce an inference report to what the build-runtime page needs: the build
 * target's first candidate as a single self-contained shell script to load into
 * the editor, or a not-inferred outcome. Pure so the choice is unit-testable
 * without the API.
 *
 * When the build target is a decision (several viable strategies), the first
 * candidate is chosen as the one to load; the caller surfaces the alternative
 * count so the author knows others exist. Build surfaces no blocking warnings
 * yet, so `blockingMessages` is always empty.
 */
export function selectBuildCandidate(report: InferenceReport): ScriptGeneration {
  const buildResult = findResult(report, isBuild);
  const candidates = buildResult?.candidates ?? [];
  const candidate = candidates.find(
    (entry) => typeof entry.body === "string" && entry.body.length > 0,
  );
  if (!buildResult || !candidate || typeof candidate.body !== "string") {
    return { status: "not_inferred", blockingMessages: [] };
  }
  return {
    status: "generated",
    script: {
      body: candidate.body,
      ruleId: candidate.inference_rule,
      application: candidate.application,
      alternativeCount: candidates.length,
      blockingMessages: [],
    },
  };
}

/**
 * The build target's decision trace — the executed DAG walk that explains why
 * inference did (or did not) produce a candidate. Present for every build
 * request; `null` only if the report has no build target.
 */
export function selectBuildTrace(report: InferenceReport): DecisionTrace | null {
  return traceForResult(report, isBuild);
}

/**
 * The static build-inference DAG (the full graph) the build trace overlays onto,
 * matched by key. `null` if the report shipped no matching DAG.
 */
export function selectBuildDag(report: InferenceReport): DecisionDag | null {
  return dagForTrace(report, selectBuildTrace(report));
}
