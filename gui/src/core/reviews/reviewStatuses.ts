import type { ReviewStepKey } from "@core/generated/vocabulary";
import type { ReviewAttempt, ReviewStepState } from "./Review";
import { REVIEW_STEPS, type ReviewStepStatus, reviewStep } from "./reviewDag";

export function reviewStepStatuses(
  attempt: ReviewAttempt | undefined,
  options: { pendingStep?: ReviewStepKey } = {},
): Record<ReviewStepKey, ReviewStepStatus> {
  const statuses = {} as Record<ReviewStepKey, ReviewStepStatus>;
  for (const step of REVIEW_STEPS) {
    statuses[step.key] = stepStatus(attempt, step.key, statuses);
  }
  if (options.pendingStep) statuses[options.pendingStep] = "queued";
  return statuses;
}

export function selectReviewAttempt(
  attempts: readonly ReviewAttempt[] | undefined,
  openedReviewId: string | undefined,
): { attempt: ReviewAttempt | undefined; pending: boolean } {
  const listed = attempts ?? [];
  if (!openedReviewId) return { attempt: listed[0], pending: false };
  const opened = listed.find((review) => review.reviewId === openedReviewId);
  return { attempt: opened, pending: opened == null };
}

export function runnableReviewSteps(
  statuses: Readonly<Record<ReviewStepKey, ReviewStepStatus>>,
): Set<ReviewStepKey> {
  const busy = REVIEW_STEPS.some(
    (step) => statuses[step.key] === "queued" || statuses[step.key] === "running",
  );
  if (busy) return new Set();
  return new Set(
    REVIEW_STEPS.filter((step) => statuses[step.key] !== "unavailable").map((step) => step.key),
  );
}

export function experimentReviewStatus(
  attempt: ReviewAttempt | undefined,
  experimentName: string,
  statuses: Readonly<Record<ReviewStepKey, ReviewStepStatus>>,
): ReviewStepStatus {
  const step = statuses.experiments;
  if (step === "unavailable") return "unavailable";
  const comparison = attempt?.experimentComparisons.find(
    (entry) => entry.experimentName === experimentName,
  );
  if (comparison) return comparison.verdict;
  return step === "queued" || step === "running" ? step : "ready";
}

export function reproducedExperimentCount(attempt: ReviewAttempt | undefined): number {
  return (attempt?.experimentComparisons ?? []).filter(
    (entry) => entry.verdict === "identical" || entry.verdict === "reproduced",
  ).length;
}

export function unreproducedExperiments(
  attempt: ReviewAttempt | undefined,
  experimentNames: readonly string[],
): string[] {
  const settled = new Set(
    (attempt?.experimentComparisons ?? []).map((entry) => entry.experimentName),
  );
  return experimentNames.filter((name) => !settled.has(name));
}

const EXPERIMENT_ROLLUP: readonly ReviewStepStatus[] = [
  "different",
  "inconclusive",
  "reproduced",
  "identical",
];

function experimentsRollup(attempt: ReviewAttempt): ReviewStepStatus | undefined {
  const verdicts = new Set<ReviewStepStatus>(
    attempt.experimentComparisons.map((entry) => entry.verdict),
  );
  return EXPERIMENT_ROLLUP.find((verdict) => verdicts.has(verdict));
}

const SETTLED: readonly ReviewStepStatus[] = [
  "succeeded",
  "identical",
  "equivalent",
  "different",
  "inconclusive",
];

function stepStatus(
  attempt: ReviewAttempt | undefined,
  key: ReviewStepKey,
  resolved: Partial<Record<ReviewStepKey, ReviewStepStatus>>,
): ReviewStepStatus {
  const state = attempt && findStep(attempt, key);
  if (!state) return dependenciesSettled(key, resolved) ? "ready" : "unavailable";
  if (state.status === "running") return "running";
  if (state.status === "failed" || state.status === "canceled") return "failed";
  return verdict(attempt, key) ?? "succeeded";
}

function verdict(attempt: ReviewAttempt, key: ReviewStepKey): ReviewStepStatus | undefined {
  if (key === "acquire_source") return attempt.sourceComparison?.verdict;
  if (key === "build_experiment_environment")
    return attempt.experimentEnvironmentComparison?.verdict;
  if (key === "activate_experiment_environment") {
    const outcome = attempt.activationOutcome;
    if (!outcome) return undefined;
    return outcome.verdict === "passed" ? "succeeded" : "uninhabitable";
  }
  if (key === "experiments") return experimentsRollup(attempt);
  return undefined;
}

function dependenciesSettled(
  key: ReviewStepKey,
  resolved: Partial<Record<ReviewStepKey, ReviewStepStatus>>,
): boolean {
  return reviewStep(key).dependencies.every((dependency) => {
    const status = resolved[dependency];
    return status != null && SETTLED.includes(status);
  });
}

function findStep(attempt: ReviewAttempt, key: ReviewStepKey): ReviewStepState | undefined {
  return attempt.steps.find((state) => state.step === key);
}
