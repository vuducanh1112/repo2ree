import type { DecisionDag, DecisionTrace, InferenceReport } from "@shell/infra/api/apiTypes";

// A run-target kind the build-runtime / experiment pages can generate a script
// for. Build has its own selector (buildCandidate.ts); these cover the runtime
// load/run scaffolds that share one shape.
export type RunTargetKind = "activation_run" | "experiment_run";

export interface GeneratedRunScript {
  // The rendered scaffold body to load into the editor.
  body: string;
  // The rule that produced it (e.g. "docker-runtime-activation-v1").
  ruleId: string;
  // Advisory: whether a human should confirm before saving. Inference never
  // writes, so this is advice, not a gate. Phase 1 run scaffolds are always
  // "confirmation_required" (the command is never inferred).
  application: "automatic_allowed" | "confirmation_required" | "unavailable";
  // How many candidates the target returned (>1 means several viable runtimes).
  alternativeCount: number;
  // Blocking warning messages the author must resolve before the scaffold is
  // usable (e.g. an undeclared runtime, or the missing command).
  blockingMessages: string[];
}

export type RunScriptGeneration =
  | { status: "generated"; script: GeneratedRunScript }
  // Nothing could be inferred (no resolved runtime contract, undeclared
  // experiment, ambiguous artifact, …). The trace explains why.
  | { status: "not_inferred"; blockingMessages: string[] };

type InferenceResult = NonNullable<InferenceReport["results"]>[number];

function matches(result: InferenceResult, kind: RunTargetKind, experimentName?: string): boolean {
  if (result.target.kind !== kind) return false;
  if (kind === "experiment_run") return result.target.experiment_name === experimentName;
  return true;
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
): RunScriptGeneration {
  const result = (report.results ?? []).find((r) => matches(r, kind, experimentName));
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
  const result = (report.results ?? []).find((r) => matches(r, kind, experimentName));
  return result?.decision ?? null;
}

/** The static DAG the run trace overlays onto, matched by key. */
export function selectRunDag(
  report: InferenceReport,
  kind: RunTargetKind,
  experimentName?: string,
): DecisionDag | null {
  const trace = selectRunTrace(report, kind, experimentName);
  if (!trace) return null;
  return (report.dags ?? []).find((dag) => dag.key === trace.dag) ?? null;
}
