import type { ReviewBasisRequest } from "@core/reviews/Review";
import type { RunSummary } from "@shell/infra/api/apiTypes";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

export function useStartSourceReviewMutation() {
  const runtime = useApiRuntime();
  const reeId = resolveReeId(runtime);
  const invalidate = useReviewInvalidation(reeId);

  return useMutation({
    // Resolves to the id of the attempt this opened, not to the run envelope:
    // the console has to drive *that* attempt from the moment the POST returns,
    // and the reviews list does not carry it yet (see `selectReviewAttempt`).
    mutationFn: async (basis: ReviewBasisRequest = "auto") =>
      openedReviewId(await runtime.reeApi.startSourceReview(reeId, { basis })),
    onSuccess: invalidate,
  });
}

/**
 * The attempt a review run opened.
 *
 * The route mints the id and seeds it onto the run at creation, so it is on the
 * response to this very POST — before the run executes and long before the
 * attempt appears in the reviews list. That timing is the whole point: it is
 * what lets the console address the attempt it just opened instead of guessing
 * at the newest one it can see.
 */
function openedReviewId(run: RunSummary): string | undefined {
  const reviewId = run.outputs?.review_id;
  return typeof reviewId === "string" && reviewId ? reviewId : undefined;
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
      // The rebuilt workspace is kept: activation runs in it, and on an
      // independent basis the runtime it holds exists nowhere else.
      runtime.reeApi.startBuildReview(reeId, reviewId, { prune_workspace: false, basis }),
    onSuccess: invalidate,
  });
}

/**
 * Probe the runtime the attempt certified. Deliberately has no basis parameter:
 * activation runs in the workspace the build left behind and inherits what that
 * evidence is worth, so offering the choice here would be offering a fiction.
 */
export function useStartActivationReviewMutation() {
  const runtime = useApiRuntime();
  const reeId = resolveReeId(runtime);
  const invalidate = useReviewInvalidation(reeId);

  return useMutation({
    mutationFn: ({ reviewId }: { reviewId: string }) =>
      runtime.reeApi.startActivationReview(reeId, reviewId),
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
