import type { ReviewAttempt } from "@core/reviews/Review";
import { useQuery } from "@tanstack/react-query";
import { useReeRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import { mapReviewRecord } from "./mapping";

/**
 * Review attempts for this REE.
 *
 * `enabled` is the caller's switch, not a convenience: this listing polls, and
 * the model that owns it now lives above the review surfaces rather than inside
 * them, so a workspace nobody is reviewing would otherwise poll forever.
 */
export function useReviewsQuery({ enabled = true }: { enabled?: boolean } = {}) {
  const runtime = useReeRuntime();
  const reeId = resolveReeId(runtime);

  return useQuery<ReviewAttempt[]>({
    queryKey: queryKeys.reviews(reeId),
    queryFn: async () => {
      const result = await runtime.reeApi.listReviews(reeId);
      return (result.reviews ?? []).map(mapReviewRecord);
    },
    enabled: enabled && !!runtime.reeId,
    refetchInterval: (query) =>
      query.state.data?.some((review) => review.status === "running") ? 1500 : 5000,
  });
}
