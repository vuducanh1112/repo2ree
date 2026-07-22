import type { DecisionDag, DecisionTrace, InferenceReport } from "@shell/infra/api/apiTypes";

// One inference result in a report. Both the build and run selectors reduce a
// report the same way — find the target's result, then read its candidates,
// trace, and the static DAG the trace overlays onto — so that shared shape lives
// here once instead of being re-spelled per target family.
export type InferenceResult = NonNullable<InferenceReport["results"]>[number];

/** The first result matching `predicate`, or `undefined` if the report has none. */
export function findResult(
  report: InferenceReport,
  predicate: (result: InferenceResult) => boolean,
): InferenceResult | undefined {
  return (report.results ?? []).find(predicate);
}

/** That result's executed decision trace, or `null` if the report has no such target. */
export function traceForResult(
  report: InferenceReport,
  predicate: (result: InferenceResult) => boolean,
): DecisionTrace | null {
  return findResult(report, predicate)?.decision ?? null;
}

/** The static DAG a trace overlays onto (all branches), matched by key. */
export function dagForTrace(
  report: InferenceReport,
  trace: DecisionTrace | null,
): DecisionDag | null {
  if (!trace) return null;
  return (report.dags ?? []).find((dag) => dag.key === trace.dag) ?? null;
}
