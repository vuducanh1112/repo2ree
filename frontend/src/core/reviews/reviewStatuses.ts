import type { ReviewAttempt, ReviewStepState } from "./Review";
import { REVIEW_STEPS, type ReviewStepKey, type ReviewStepStatus, reviewStep } from "./reviewDag";

/**
 * The per-step display state of a review attempt.
 *
 * A step's status is its lifecycle state until it settles, at which point the
 * *comparison verdict* takes over — "completed" says the reviewer's machine
 * finished, which is not what a reviewer wants to read. A step whose
 * dependencies have not settled is "unavailable": it has nothing to reproduce
 * against yet.
 */
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

/**
 * The attempt the console is driving, and whether the list has caught up to it.
 *
 * Starting a review returns the id of the attempt it opened before the workbench
 * has written that attempt's record, so the list lags the truth by one poll.
 * Taking the newest *listed* attempt during that gap hands back the previous
 * one — which reads as settled, because its steps are — and any step dispatched
 * against it silently certifies the wrong attempt.
 *
 * So an opened id always wins, and until it appears the answer is "not yet"
 * rather than the closest thing to hand. `pending` is what that gap is: the
 * attempt exists, this console opened it, and nothing about it can be shown or
 * acted on until it is readable.
 */
export function selectReviewAttempt(
  attempts: readonly ReviewAttempt[] | undefined,
  openedReviewId: string | undefined,
): { attempt: ReviewAttempt | undefined; pending: boolean } {
  const listed = attempts ?? [];
  if (!openedReviewId) return { attempt: listed[0], pending: false };
  const opened = listed.find((review) => review.reviewId === openedReviewId);
  return { attempt: opened, pending: opened == null };
}

/** Which steps a reviewer may start right now. */
export function runnableReviewSteps(
  statuses: Readonly<Record<ReviewStepKey, ReviewStepStatus>>,
): Set<ReviewStepKey> {
  const busy = REVIEW_STEPS.some(
    (step) => statuses[step.key] === "queued" || statuses[step.key] === "running",
  );
  if (busy) return new Set();
  // Source opens an attempt, so it is always available; every other step needs
  // its dependencies settled — and only source is implemented beyond build.
  return new Set(
    REVIEW_STEPS.filter(
      (step) => statuses[step.key] !== "unavailable" && IMPLEMENTED_STEPS.has(step.key),
    ).map((step) => step.key),
  );
}

/** Steps with a reviewer-side path today; the rest stay disabled in the DAG. */
const IMPLEMENTED_STEPS = new Set<ReviewStepKey>(["source", "build", "activation"]);

/**
 * Statuses a dependent step may build on.
 *
 * `different` and `inconclusive` are here because a divergent runtime is still
 * worth probing — "does the thing we got actually run?" is a fair question
 * about a build that did not match. `uninhabitable` is deliberately absent:
 * running experiments inside a runtime that would not come up produces failures
 * that say nothing about the experiments.
 */
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
  if (key === "source") return attempt.sourceComparison?.verdict;
  if (key === "build") return attempt.buildComparison?.verdict;
  if (key === "activation") {
    const outcome = attempt.activationOutcome;
    if (!outcome) return undefined;
    return outcome.verdict === "passed" ? "succeeded" : "uninhabitable";
  }
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
