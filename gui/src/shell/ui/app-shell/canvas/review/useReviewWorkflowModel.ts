import type { ReviewStepKey } from "@core/generated/vocabulary";
import type { ReeExperiment } from "@core/ree/ReeSpec";
import type { ReviewAttempt, ReviewBasisRequest } from "@core/reviews/Review";
import { settledReviewStepCount } from "@core/reviews/reviewDag";
import {
  reviewStepStatuses,
  runnableReviewSteps,
  selectReviewAttempt,
  unreproducedExperiments,
} from "@core/reviews/reviewStatuses";
import {
  useStartActivationReviewMutation,
  useStartBuildExperimentEnvironmentReviewMutation,
  useStartExperimentReviewMutation,
  useStartSourceReviewMutation,
} from "@shell/data/reviews/mutations";
import { useReviewsQuery } from "@shell/data/reviews/queries";
import { useEffect, useState } from "react";

export interface ReviewWorkflowModel {
  attempt: ReviewAttempt | undefined;
  statuses: ReturnType<typeof reviewStepStatuses>;
  enabledSteps: ReadonlySet<ReviewStepKey>;
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

export function useReviewWorkflowModel({
  experiments,
  active,
}: {
  experiments: readonly ReeExperiment[];
  active: boolean;
}): ReviewWorkflowModel {
  const [basis, setBasis] = useState<ReviewBasisRequest>("auto");
  const reviews = useReviewsQuery({ enabled: active });
  const reviewAcquireSource = useStartSourceReviewMutation();
  const reviewBuildExperimentEnvironment = useStartBuildExperimentEnvironmentReviewMutation();
  const reviewActivateExperimentEnvironment = useStartActivationReviewMutation();
  const reviewRunExperiment = useStartExperimentReviewMutation();
  const [sweep, setSweep] = useState<readonly string[] | undefined>();
  const [dispatched, setDispatched] = useState<string | undefined>();
  const openedReviewId = reviewAcquireSource.data;
  const { attempt, pending } = selectReviewAttempt(reviews.data, openedReviewId);

  const pendingStep: ReviewStepKey | undefined = reviewAcquireSource.isPending
    ? "acquire_source"
    : reviewBuildExperimentEnvironment.isPending
      ? "build_experiment_environment"
      : reviewActivateExperimentEnvironment.isPending
        ? "activate_experiment_environment"
        : reviewRunExperiment.isPending
          ? "experiments"
          : pending
            ? "acquire_source"
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
    reviewRunExperiment.mutate({ reviewId: attempt.reviewId, experimentName });
  };

  const remaining = unreproducedExperiments(attempt, experimentNames);
  const runAllExperiments = () => {
    if (!attempt || !enabledSteps.has("experiments") || remaining.length === 0) return;
    setSweep(remaining);
  };

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
    if (attempt.status === "failed") {
      setSweep(undefined);
      setDispatched(undefined);
      return;
    }
    if (next === dispatched || reviewRunExperiment.isPending) return;
    setDispatched(next);
    reviewRunExperiment.mutate({ reviewId: attempt.reviewId, experimentName: next });
  }, [sweep, attempt, dispatched, reviewRunExperiment]);

  const invokeStep = (step: ReviewStepKey) => {
    if (!enabledSteps.has(step)) return;
    if (step === "acquire_source") reviewAcquireSource.mutate(basis);
    if (step === "build_experiment_environment" && attempt)
      reviewBuildExperimentEnvironment.mutate({ reviewId: attempt.reviewId, basis });
    if (step === "activate_experiment_environment" && attempt)
      reviewActivateExperimentEnvironment.mutate({ reviewId: attempt.reviewId });
    if (step === "experiments") runAllExperiments();
  };

  const error =
    reviewAcquireSource.error ??
    reviewBuildExperimentEnvironment.error ??
    reviewActivateExperimentEnvironment.error ??
    reviewRunExperiment.error ??
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
