import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveWorkspaceId } from "../client";
import { queryKeys } from "../queryKeys";
import { useWorkspaceClient } from "./client";

export function useUpdateReeDraftMutation(workspaceId?: string) {
  const runtime = useApiRuntime();
  const workspaceClient = useWorkspaceClient();
  const queryClient = useQueryClient();
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);

  return useMutation({
    mutationFn: (reePatch: Record<string, unknown>) =>
      workspaceClient.updateReeDraft(resolvedWorkspaceId, reePatch),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.ree(resolvedWorkspaceId),
      });
    },
  });
}
