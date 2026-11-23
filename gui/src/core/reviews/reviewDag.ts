import type { ReviewStepKey } from "@core/generated/vocabulary";

export type ReviewStepStatus =
  | "unavailable"
  | "ready"
  | "queued"
  | "running"
  | "succeeded"
  | "identical"
  | "equivalent"
  | "reproduced"
  | "different"
  | "inconclusive"
  | "uninhabitable"
  | "failed";

interface ReviewStepDefinition {
  key: ReviewStepKey;
  label: string;
  dependencies: readonly ReviewStepKey[];
}

export const REVIEW_STEPS: readonly ReviewStepDefinition[] = [
  { key: "acquire_source", label: "Source", dependencies: [] },
  {
    key: "build_experiment_environment",
    label: "Build Experiment Environment",
    dependencies: ["acquire_source"],
  },
  {
    key: "activate_experiment_environment",
    label: "Activation",
    dependencies: ["build_experiment_environment"],
  },
  { key: "experiments", label: "Experiments", dependencies: ["activate_experiment_environment"] },
];

export function reviewStep(key: ReviewStepKey): ReviewStepDefinition {
  const step = REVIEW_STEPS.find((candidate) => candidate.key === key);
  if (!step) throw new Error(`Unknown review step: ${key}`);
  return step;
}

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
