export type ReviewStepKey = "source" | "build" | "activation" | "experiments";

export type ReviewStepStatus =
  | "unavailable"
  | "ready"
  | "queued"
  | "running"
  | "succeeded"
  | "identical"
  | "equivalent"
  | "different"
  | "inconclusive"
  | "failed";

interface ReviewStepDefinition {
  key: ReviewStepKey;
  label: string;
  dependencies: readonly ReviewStepKey[];
}

/**
 * The independently runnable review lifecycle. Materialization remains an
 * implementation detail of source acquisition: it creates no evidence of its
 * own, so it does not get a button in the reviewer-facing graph.
 */
export const REVIEW_STEPS: readonly ReviewStepDefinition[] = [
  { key: "source", label: "Source", dependencies: [] },
  { key: "build", label: "Build", dependencies: ["source"] },
  { key: "activation", label: "Activation", dependencies: ["build"] },
  { key: "experiments", label: "Experiments", dependencies: ["activation"] },
];

export function reviewStep(key: ReviewStepKey): ReviewStepDefinition {
  const step = REVIEW_STEPS.find((candidate) => candidate.key === key);
  if (!step) throw new Error(`Unknown review step: ${key}`);
  return step;
}

/** Stable topological order used by the whole-lifecycle runner. */
export function reviewLifecycleOrder(): ReviewStepKey[] {
  const visited = new Set<ReviewStepKey>();
  const ordered: ReviewStepKey[] = [];

  function visit(key: ReviewStepKey) {
    if (visited.has(key)) return;
    for (const dependency of reviewStep(key).dependencies) visit(dependency);
    visited.add(key);
    ordered.push(key);
  }

  for (const step of REVIEW_STEPS) visit(step.key);
  return ordered;
}

export function settledReviewStepCount(
  statuses: Readonly<Partial<Record<ReviewStepKey, ReviewStepStatus>>>,
): number {
  return REVIEW_STEPS.filter((step) => {
    const status = statuses[step.key];
    return status != null && !["unavailable", "ready", "queued", "running"].includes(status);
  }).length;
}
