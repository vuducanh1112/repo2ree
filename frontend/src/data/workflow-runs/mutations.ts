import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveWorkspaceId } from "../client";
import { queryKeys } from "../queryKeys";
import { useWorkflowRunsClient } from "./client";

type WorkflowRunParams = Record<string, string | boolean | number | null | undefined>;

export function useStartWorkflowRunMutation(workspaceId?: string) {
  const runtime = useApiRuntime();
  const workflowRunsClient = useWorkflowRunsClient();
  const queryClient = useQueryClient();
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);

  return useMutation({
    mutationFn: ({ scriptKey, params = {} }: { scriptKey: string; params?: WorkflowRunParams }) =>
      workflowRunsClient.startWorkflowRun(resolvedWorkspaceId, scriptKey, params),
    onSuccess: async (run) => {
      queryClient.setQueryData(queryKeys.workflowRun(resolvedWorkspaceId, run.runId), run);
      await queryClient.invalidateQueries({
        queryKey: queryKeys.workflowRun(resolvedWorkspaceId, run.runId),
      });
    },
  });
}

export function useCancelWorkflowRunMutation(workspaceId?: string) {
  const runtime = useApiRuntime();
  const workflowRunsClient = useWorkflowRunsClient();
  const queryClient = useQueryClient();
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);

  return useMutation({
    mutationFn: async ({ runId }: { runId: string }) => {
      const status = await workflowRunsClient.cancelWorkflowRun(resolvedWorkspaceId, runId);
      return { runId, status };
    },
    onSuccess: async ({ runId }) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.workflowRun(resolvedWorkspaceId, runId),
      });
    },
  });
}
