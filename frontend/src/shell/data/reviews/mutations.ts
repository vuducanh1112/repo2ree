import type { ReviewBasisRequest } from "@core/reviews/Review";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

export function useStartSourceReviewMutation() {
  const runtime = useApiRuntime();
  const reeId = resolveReeId(runtime);
  const invalidate = useReviewInvalidation(reeId);

  return useMutation({
    mutationFn: (basis: ReviewBasisRequest = "auto") =>
      runtime.reeApi.startSourceReview(reeId, { basis }),
    onSuccess: invalidate,
  });
}

/**
 * Certify the runtime inside an existing attempt. Takes the review id at call
 * time rather than at hook time: the attempt to build in is whichever one the
 * source step opened, which is not known when the console mounts.
 */
export function useStartBuildReviewMutation() {
  const runtime = useApiRuntime();
  const reeId = resolveReeId(runtime);
  const invalidate = useReviewInvalidation(reeId);

  return useMutation({
    mutationFn: ({ reviewId, basis = "auto" }: { reviewId: string; basis?: ReviewBasisRequest }) =>
      // prune_workspace is stated rather than defaulted: the console has no
      // activation step to hand the rebuilt runtime to yet, so the attempt
      // reclaims it once the verdict is recorded.
      runtime.reeApi.startBuildReview(reeId, reviewId, { prune_workspace: true, basis }),
    onSuccess: invalidate,
  });
}

/** Both review mutations move the same two lists: the attempts and the runs. */
function useReviewInvalidation(reeId: string) {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.reviews(reeId) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.reeRuns(reeId) }),
    ]);
  };
}
