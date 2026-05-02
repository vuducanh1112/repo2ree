import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useWorkspaceRuntime } from "../../app/browser/BrowserRuntime";
import { resolveWorkspaceId } from "../client";
import { queryKeys } from "../queryKeys";

export function useUpdateReeDraftMutation(workspaceId?: string) {
  const runtime = useWorkspaceRuntime();
  const queryClient = useQueryClient();
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);

  return useMutation({
    mutationFn: (reePatch: Record<string, unknown>) =>
      runtime.workspaceRepository.updateReeDraft(resolvedWorkspaceId, reePatch),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.ree(resolvedWorkspaceId),
      });
    },
  });
}
