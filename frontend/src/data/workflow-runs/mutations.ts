import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import { useWorkflowRunsClient } from "./client";

type WorkflowRunParams = Record<string, string | boolean | number | null | undefined>;

export function useStartWorkflowRunMutation(reeId?: string) {
  const runtime = useApiRuntime();
  const workflowRunsClient = useWorkflowRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation({
    mutationFn: ({ scriptKey, params = {} }: { scriptKey: string; params?: WorkflowRunParams }) =>
      workflowRunsClient.startWorkflowRun(resolvedReeId, scriptKey, params),
    onSuccess: async (run) => {
      queryClient.setQueryData(queryKeys.workflowRun(resolvedReeId, run.runId), run);
      await queryClient.invalidateQueries({
        queryKey: queryKeys.workflowRun(resolvedReeId, run.runId),
      });
    },
  });
}

export function useCancelWorkflowRunMutation(reeId?: string) {
  const runtime = useApiRuntime();
  const workflowRunsClient = useWorkflowRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation({
    mutationFn: async ({ runId }: { runId: string }) => {
      const status = await workflowRunsClient.cancelWorkflowRun(resolvedReeId, runId);
      return { runId, status };
    },
    onSuccess: async ({ runId }) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.workflowRun(resolvedReeId, runId),
      });
    },
  });
}
