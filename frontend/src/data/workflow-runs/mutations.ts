import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useWorkspaceRuntime } from "../../app/browser/BrowserRuntime";
import { resolveWorkspaceId } from "../client";
import { queryKeys } from "../queryKeys";

type WorkflowRunParams = Record<string, string | boolean | number | null | undefined>;

export function useStartWorkflowRunMutation(workspaceId?: string) {
  const runtime = useWorkspaceRuntime();
  const queryClient = useQueryClient();
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);

  return useMutation({
    mutationFn: ({ scriptKey, params = {} }: { scriptKey: string; params?: WorkflowRunParams }) =>
      runtime.workflowRunRepository.startWorkflowRun(resolvedWorkspaceId, scriptKey, params),
    onSuccess: async (run) => {
      queryClient.setQueryData(queryKeys.workflowRun(resolvedWorkspaceId, run.runId), run);
      await queryClient.invalidateQueries({
        queryKey: queryKeys.workflowRun(resolvedWorkspaceId, run.runId),
      });
    },
  });
}

export function useCancelWorkflowRunMutation(workspaceId?: string) {
  const runtime = useWorkspaceRuntime();
  const queryClient = useQueryClient();
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);

  return useMutation({
    mutationFn: async ({ runId }: { runId: string }) => {
      const status = await runtime.workflowRunRepository.cancelWorkflowRun(
        resolvedWorkspaceId,
        runId,
      );
      return { runId, status };
    },
    onSuccess: async ({ runId }) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.workflowRun(resolvedWorkspaceId, runId),
      });
    },
  });
}
