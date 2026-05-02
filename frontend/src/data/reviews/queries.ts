import { queryOptions, useQuery } from "@tanstack/react-query";
import { useWorkspaceRuntime, type WorkspaceRuntimeValue } from "../../app/browser/BrowserRuntime";
import { queryKeys } from "../queryKeys";

function createReviewQueryOptions(runtime: WorkspaceRuntimeValue, reviewId: string) {
  return queryOptions({
    queryKey: queryKeys.review(reviewId),
    queryFn: () => runtime.reviewRepository.getReview(reviewId),
  });
}

export function useReviewQuery(reviewId?: string) {
  const runtime = useWorkspaceRuntime();

  return useQuery({
    ...(reviewId
      ? createReviewQueryOptions(runtime, reviewId)
      : {
          queryKey: queryKeys.review("idle"),
          queryFn: async () => {
            throw new Error("Review query is disabled");
          },
        }),
    enabled: !!reviewId,
  });
}
