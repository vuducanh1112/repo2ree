import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import { useExecutionRunsClient } from "./client";

type ExecutionRunParams = Record<string, string | boolean | number | null | undefined>;

export function useStartExecutionRunMutation(reeId?: string) {
  const runtime = useApiRuntime();
  const executionRunsClient = useExecutionRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation({
    mutationFn: ({ scriptKey, params = {} }: { scriptKey: string; params?: ExecutionRunParams }) =>
      executionRunsClient.startExecutionRun(resolvedReeId, scriptKey, params),
    onSuccess: async (run) => {
      queryClient.setQueryData(queryKeys.workflowRun(resolvedReeId, run.runId), run);
      await queryClient.invalidateQueries({
        queryKey: queryKeys.workflowRun(resolvedReeId, run.runId),
      });
    },
  });
}

export function useCancelExecutionRunMutation(reeId?: string) {
  const runtime = useApiRuntime();
  const executionRunsClient = useExecutionRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation({
    mutationFn: async ({ runId }: { runId: string }) => {
      const status = await executionRunsClient.cancelExecutionRun(resolvedReeId, runId);
      return { runId, status };
    },
    onSuccess: async ({ runId }) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.workflowRun(resolvedReeId, runId),
      });
    },
  });
}
