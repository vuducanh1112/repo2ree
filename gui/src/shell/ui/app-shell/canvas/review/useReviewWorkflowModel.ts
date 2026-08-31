import type { ReeExperiment } from "@core/ree/ReeSpec";
import type { ReviewAttempt, ReviewBasisRequest } from "@core/reviews/Review";
import { type ReviewStepKey, settledReviewStepCount } from "@core/reviews/reviewDag";
import {
  reviewStepStatuses,
  runnableReviewSteps,
  selectReviewAttempt,
  unreproducedExperiments,
} from "@core/reviews/reviewStatuses";
import {
  useStartActivationReviewMutation,
  useStartBuildReviewMutation,
  useStartExperimentReviewMutation,
  useStartSourceReviewMutation,
} from "@shell/data/reviews/mutations";
import { useReviewsQuery } from "@shell/data/reviews/queries";
import { useEffect, useState } from "react";

export interface ReviewWorkflowModel {
  /** The attempt this console opened, or the newest one on record. */
  attempt: ReviewAttempt | undefined;
  statuses: ReturnType<typeof reviewStepStatuses>;
  enabledSteps: ReadonlySet<ReviewStepKey>;
  /** Steps that have settled, for the workflow toggle's counter. */
  complete: number;
  running: boolean;
  basis: ReviewBasisRequest;
  setBasis: (basis: ReviewBasisRequest) => void;
  invokeStep: (step: ReviewStepKey) => void;
  runExperiment: (experimentName: string) => void;
  runAllExperiments: () => void;
  sweeping: boolean;
  experimentNames: readonly string[];
  error: unknown;
}

/**
 * The reviewer's whole workflow state, owned above the surfaces that show it.
 *
 * The strip in the status bar and the evidence drawer are two views of one
 * attempt, so the attempt cannot live in either of them. `active` gates the
 * listing poll: reviews are polled every 5s (1.5s while a step runs), and a
 * workspace nobody is reviewing should not pay for that.
 */
export function useReviewWorkflowModel({
  experiments,
  active,
}: {
  experiments: readonly ReeExperiment[];
  active: boolean;
}): ReviewWorkflowModel {
  // What the next step reproduces from. "auto" takes the strongest basis the
  // baseline supports; "bundled" is the deliberate choice to certify what the
  // REE already carries, which is the only path open for a bundle with no
  // reachable origin — and the weaker verdict, so it is never the default.
  const [basis, setBasis] = useState<ReviewBasisRequest>("auto");
  const reviews = useReviewsQuery({ enabled: active });
  const startSourceReview = useStartSourceReviewMutation();
  const startBuildReview = useStartBuildReviewMutation();
  const startActivationReview = useStartActivationReviewMutation();
  const startExperimentReview = useStartExperimentReviewMutation();
  // The names a "run all" sweep still has to get through, and the one it has
  // already dispatched. Experiments share a workspace, so they must run one at
  // a time; the sweep advances on evidence (a verdict appearing) rather than on
  // the POST resolving, which only means the run was accepted.
  const [sweep, setSweep] = useState<readonly string[] | undefined>();
  const [dispatched, setDispatched] = useState<string | undefined>();
  // The attempt this console opened, named by the run that opened it. Preferred
  // over the newest listed attempt because the list lags: the workbench writes
  // the record a moment after the POST returns, and every step dispatched in
  // that gap would join the *previous* attempt instead.
  const openedReviewId = startSourceReview.data;
  const { attempt, pending } = selectReviewAttempt(reviews.data, openedReviewId);

  const pendingStep: ReviewStepKey | undefined = startSourceReview.isPending
    ? "source"
    : startBuildReview.isPending
      ? "build"
      : startActivationReview.isPending
        ? "activation"
        : startExperimentReview.isPending
          ? "experiments"
          : // An attempt opened but not yet readable is the source step still
            // going, which also keeps every later step disabled until it lands.
            pending
            ? "source"
            : undefined;
  const statuses = reviewStepStatuses(attempt, { pendingStep });
  const enabledSteps = runnableReviewSteps(statuses);
  const complete = settledReviewStepCount(statuses);
  const running = pendingStep != null || attempt?.status === "running";

  const experimentNames = experiments
    .map((experiment) => experiment.name.trim())
    .filter((name) => name.length > 0);

  const runExperiment = (experimentName: string) => {
    if (!attempt || !enabledSteps.has("experiments")) return;
    startExperimentReview.mutate({ reviewId: attempt.reviewId, experimentName });
  };

  // A sweep covers what has no verdict yet rather than everything declared:
  // re-running a settled experiment is a deliberate act, and the per-experiment
  // "Re-run" is where it belongs.
  const remaining = unreproducedExperiments(attempt, experimentNames);
  const runAllExperiments = () => {
    if (!attempt || !enabledSteps.has("experiments") || remaining.length === 0) return;
    setSweep(remaining);
  };

  // Drive a sweep one experiment at a time. The next one goes out only once the
  // previous has a verdict on the record, because the POST resolving means the
  // run was accepted rather than finished — and two experiments running at once
  // would write over each other's outputs in the shared workspace.
  useEffect(() => {
    if (!sweep || !attempt) return;
    const next = sweep.find(
      (name) => !attempt.experimentComparisons.some((entry) => entry.experimentName === name),
    );
    if (next === undefined) {
      setSweep(undefined);
      setDispatched(undefined);
      return;
    }
    // A step that failed produces no verdict, so waiting for one would stall the
    // sweep in silence. Stop instead and leave the failure on screen.
    if (attempt.status === "failed") {
      setSweep(undefined);
      setDispatched(undefined);
      return;
    }
    if (next === dispatched || startExperimentReview.isPending) return;
    setDispatched(next);
    startExperimentReview.mutate({ reviewId: attempt.reviewId, experimentName: next });
  }, [sweep, attempt, dispatched, startExperimentReview]);

  const invokeStep = (step: ReviewStepKey) => {
    if (!enabledSteps.has(step)) return;
    if (step === "source") startSourceReview.mutate(basis);
    // Build joins the attempt source opened; without one there is nothing to
    // build against, which is also why the DAG leaves it disabled until then.
    if (step === "build" && attempt) startBuildReview.mutate({ reviewId: attempt.reviewId, basis });
    // Activation takes no basis: it probes whatever runtime the build left in
    // the attempt's workspace and inherits what that evidence is worth.
    if (step === "activation" && attempt)
      startActivationReview.mutate({ reviewId: attempt.reviewId });
    // The graph node stands for the whole set, so it sweeps; one experiment at
    // a time is the panel's job.
    if (step === "experiments") runAllExperiments();
  };

  const error =
    startSourceReview.error ??
    startBuildReview.error ??
    startActivationReview.error ??
    startExperimentReview.error ??
    reviews.error;

  return {
    attempt,
    statuses,
    enabledSteps,
    complete,
    running,
    basis,
    setBasis,
    invokeStep,
    runExperiment,
    runAllExperiments,
    sweeping: sweep != null,
    experimentNames,
    error,
  };
}
