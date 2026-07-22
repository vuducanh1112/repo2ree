import type { DecisionDag, DecisionTrace, InferenceReport } from "@shell/infra/api/apiTypes";

export interface GeneratedBuildScript {
  // The rendered build-script body to load into the editor.
  body: string;
  // The rule that produced it (e.g. "single-project-root-dockerfile-v1" or
  // "root-pip-requirements-v1").
  ruleId: string;
  // Advisory: whether a human should confirm a strategy choice before saving.
  // Inference never writes, so this is advice, not a gate.
  application: "automatic_allowed" | "confirmation_required" | "unavailable";
  // How many candidates the build target returned. More than one means the
  // repository offered several runtime strategies — a decision, not a default.
  alternativeCount: number;
}

export type BuildScriptGeneration =
  | { status: "generated"; script: GeneratedBuildScript }
  // No candidate could be generated (e.g. no Dockerfile / requirements.txt, or
  // an ambiguous or blocked repository shape). The trace explains why.
  | { status: "not_inferred" };

/**
 * Reduce an inference report to what the build-runtime page needs: the build
 * target's first candidate as a single self-contained shell script to load into
 * the editor, or a not-inferred outcome. Pure so the choice is unit-testable
 * without the API.
 *
 * When the build target is a decision (several viable strategies), the first
 * candidate is chosen as the one to load; the caller surfaces the alternative
 * count so the author knows others exist.
 */
export function selectBuildCandidate(report: InferenceReport): BuildScriptGeneration {
  const buildResult = (report.results ?? []).find((result) => result.target.kind === "build");
  const candidates = buildResult?.candidates ?? [];
  const candidate = candidates.find(
    (entry) => typeof entry.body === "string" && entry.body.length > 0,
  );
  if (!buildResult || !candidate || typeof candidate.body !== "string") {
    return { status: "not_inferred" };
  }
  return {
    status: "generated",
    script: {
      body: candidate.body,
      ruleId: candidate.inference_rule,
      application: candidate.application,
      alternativeCount: candidates.length,
    },
  };
}

/**
 * The build target's decision trace — the executed DAG walk that explains why
 * inference did (or did not) produce a candidate. Present for every build
 * request; `null` only if the report has no build target.
 */
export function selectBuildTrace(report: InferenceReport): DecisionTrace | null {
  const buildResult = (report.results ?? []).find((result) => result.target.kind === "build");
  return buildResult?.decision ?? null;
}

/**
 * The static build-inference DAG (the full graph) the build trace overlays onto,
 * matched by key. `null` if the report shipped no matching DAG.
 */
export function selectBuildDag(report: InferenceReport): DecisionDag | null {
  const trace = selectBuildTrace(report);
  if (!trace) return null;
  return (report.dags ?? []).find((dag) => dag.key === trace.dag) ?? null;
}
