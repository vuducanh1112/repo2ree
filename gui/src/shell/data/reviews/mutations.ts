import type { ReviewBasisRequest } from "@core/reviews/Review";
import type { RunSummary } from "@shell/infra/api/apiTypes";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useReeRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

export function useStartSourceReviewMutation() {
  const runtime = useReeRuntime();
  const reeId = resolveReeId(runtime);
  const invalidate = useReviewInvalidation(reeId);

  return useMutation({
    mutationFn: async (basis: ReviewBasisRequest = "auto") =>
      openedReviewId(await runtime.reeApi.reviewAcquireSource(reeId, { basis })),
    onSuccess: invalidate,
  });
}

function openedReviewId(run: RunSummary): string | undefined {
  const reviewId = run.outputs?.review_id;
  return typeof reviewId === "string" && reviewId ? reviewId : undefined;
}

export function useStartBuildExperimentEnvironmentReviewMutation() {
  const runtime = useReeRuntime();
  const reeId = resolveReeId(runtime);
  const invalidate = useReviewInvalidation(reeId);

  return useMutation({
    mutationFn: ({ reviewId, basis = "auto" }: { reviewId: string; basis?: ReviewBasisRequest }) =>
      runtime.reeApi.reviewBuildExperimentEnvironment(reeId, reviewId, {
        basis,
      }),
    onSuccess: invalidate,
  });
}

export function useStartActivationReviewMutation() {
  const runtime = useReeRuntime();
  const reeId = resolveReeId(runtime);
  const invalidate = useReviewInvalidation(reeId);

  return useMutation({
    mutationFn: ({ reviewId }: { reviewId: string }) =>
      runtime.reeApi.reviewActivateExperimentEnvironment(reeId, reviewId),
    onSuccess: invalidate,
  });
}

export function useStartExperimentReviewMutation() {
  const runtime = useReeRuntime();
  const reeId = resolveReeId(runtime);
  const invalidate = useReviewInvalidation(reeId);

  return useMutation({
    mutationFn: ({ reviewId, experimentName }: { reviewId: string; experimentName: string }) =>
      runtime.reeApi.reviewRunExperiment(reeId, reviewId, experimentName),
    onSuccess: invalidate,
  });
}

function useReviewInvalidation(reeId: string) {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.reviews(reeId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.reeRuns(reeId) }),
    ]);
  };
}
