import type { ReviewAttempt } from "@core/reviews/Review";
import { useQuery } from "@tanstack/react-query";
import { useReeRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import { mapReviewRecord } from "./mapping";

export function useReviewsQuery() {
  const runtime = useReeRuntime();
  const reeId = resolveReeId(runtime);

  return useQuery<ReviewAttempt[]>({
    queryKey: queryKeys.reviews(reeId),
    queryFn: async () => {
      const result = await runtime.reeApi.listReviews(reeId);
      return (result.reviews ?? []).map(mapReviewRecord);
    },
    enabled: !!runtime.reeId,
    refetchInterval: (query) =>
      query.state.data?.some((review) => review.status === "running") ? 1500 : 5000,
  });
}
