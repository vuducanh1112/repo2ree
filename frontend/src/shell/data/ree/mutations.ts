import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReeIntentPatch } from "../../../core/ree/reePatch";
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
    mutationFn: (intentPatch: ReeIntentPatch) =>
      reeClient.updateReeDraft(resolvedReeId, intentPatch),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.ree(resolvedReeId),
      });
    },
  });
}
