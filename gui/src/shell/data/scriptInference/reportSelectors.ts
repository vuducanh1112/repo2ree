import type { DecisionDag, DecisionTrace, InferenceReport } from "@shell/infra/api/apiTypes";

export type InferenceResult = NonNullable<InferenceReport["results"]>[number];

export function findResult(
  report: InferenceReport,
  predicate: (result: InferenceResult) => boolean,
): InferenceResult | undefined {
  return (report.results ?? []).find(predicate);
}

export function traceForResult(
  report: InferenceReport,
  predicate: (result: InferenceResult) => boolean,
): DecisionTrace | null {
  return findResult(report, predicate)?.decision ?? null;
}

export function dagForTrace(
  report: InferenceReport,
  trace: DecisionTrace | null,
): DecisionDag | null {
  if (!trace) return null;
  return (report.dags ?? []).find((dag) => dag.key === trace.dag) ?? null;
}
