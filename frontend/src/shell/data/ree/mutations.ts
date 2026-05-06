import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import { useReeClient } from "./client";

export function useUpdateReeDraftMutation(reeId?: string) {
  const runtime = useApiRuntime();
  const reeClient = useReeClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation({
    mutationFn: (reePatch: Record<string, unknown>) =>
      reeClient.updateReeDraft(resolvedReeId, reePatch),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.ree(resolvedReeId),
      });
    },
  });
}
