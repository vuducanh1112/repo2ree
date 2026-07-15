import type { ReeIntentPatch } from "@core/ree/reePatch";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import { useReeClient } from "./client";

export function useUpdateReeIntentMutation(reeId?: string) {
  const runtime = useApiRuntime();
  const reeClient = useReeClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation({
    mutationFn: (intentPatch: ReeIntentPatch) =>
      reeClient.updateReeIntent(resolvedReeId, intentPatch),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.ree(resolvedReeId),
      });
      // Intent fields (swhid, runtime, experiments…) feed the scorecard.
      await queryClient.invalidateQueries({
        queryKey: queryKeys.scorecard(resolvedReeId),
      });
    },
  });
}
