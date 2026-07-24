import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

export function useStartSourceReviewMutation() {
  const runtime = useApiRuntime();
  const reeId = resolveReeId(runtime);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => runtime.reeApi.startSourceReview(reeId, {}),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.reviews(reeId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.reeRuns(reeId) }),
      ]);
    },
  });
}
