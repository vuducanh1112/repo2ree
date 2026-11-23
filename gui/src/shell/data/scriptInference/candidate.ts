import type { ScriptKind } from "@core/generated/vocabulary";
import type { DecisionDag, DecisionTrace, InferenceReport } from "@shell/infra/api/apiTypes";
import type { ScriptGeneration } from "./generation";
import { dagForTrace, findResult, type InferenceResult, traceForResult } from "./reportSelectors";

const SCRIPT_TARGET_KINDS = [
  "build_experiment_environment",
  "activate_experiment_environment",
  "experiment_run",
] as const satisfies readonly ScriptKind[];

export type ScriptTargetKind = (typeof SCRIPT_TARGET_KINDS)[number];

function matches(kind: ScriptTargetKind, experimentName?: string) {
  return (result: InferenceResult): boolean => {
    if (result.target.kind !== kind) return false;
    if (kind === "experiment_run") return result.target.experiment_name === experimentName;
    return true;
  };
}

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
  const experimentEnvironmentPath = candidate.dependencies?.find(
    (dep) => dep.kind === "experiment_environment_declaration",
  )?.path;
  return {
    status: "generated",
    script: {
      body: candidate.body,
      ruleId: candidate.inference_rule,
      application: candidate.application,
      alternativeCount: candidates.length,
      blockingMessages,
      experimentEnvironmentPath: experimentEnvironmentPath ?? undefined,
    },
  };
}

export function selectTrace(
  report: InferenceReport,
  kind: ScriptTargetKind,
  experimentName?: string,
): DecisionTrace | null {
  return traceForResult(report, matches(kind, experimentName));
}

export function selectDag(
  report: InferenceReport,
  kind: ScriptTargetKind,
  experimentName?: string,
): DecisionDag | null {
  return dagForTrace(report, selectTrace(report, kind, experimentName));
}
