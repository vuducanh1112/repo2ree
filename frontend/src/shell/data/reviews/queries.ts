import { queryOptions, useQuery } from "@tanstack/react-query";
import { queryKeys } from "../queryKeys";
import { useReviewClient } from "./client";

function createReviewQueryOptions(
  reviewClient: ReturnType<typeof useReviewClient>,
  reviewId: string,
) {
  return queryOptions({
    queryKey: queryKeys.review(reviewId),
    queryFn: () => reviewClient.getReview(reviewId),
  });
}

export function useReviewQuery(reviewId?: string) {
  const reviewClient = useReviewClient();

  return useQuery({
    ...(reviewId
      ? createReviewQueryOptions(reviewClient, reviewId)
      : {
          queryKey: queryKeys.review("idle"),
          queryFn: async () => {
            throw new Error("Review query is disabled");
          },
        }),
    enabled: !!reviewId,
  });
}
