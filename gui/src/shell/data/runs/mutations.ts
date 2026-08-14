import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useReeRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import { useReeRunsClient } from "./client";

type ReeRunParams = Record<string, string | boolean | number | null | undefined>;

export function useStartReeRunMutation(reeId?: string) {
  const runtime = useReeRuntime();
  const executionRunsClient = useReeRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation({
    mutationFn: ({ scriptKey, params = {} }: { scriptKey: string; params?: ReeRunParams }) =>
      executionRunsClient.startReeRun(resolvedReeId, scriptKey, params),
    onSuccess: async (run) => {
      queryClient.setQueryData(queryKeys.stepRuns(resolvedReeId, run.runId), run);
      await queryClient.invalidateQueries({
        queryKey: queryKeys.stepRuns(resolvedReeId, run.runId),
      });
    },
  });
}

/**
 * Start one named experiment's run. Seeds the run cache with what the POST
 * already returned, so the surface observing it renders from that answer
 * instead of spending another round-trip re-fetching it.
 */
export function useStartExperimentRunMutation(reeId?: string) {
  const runtime = useReeRuntime();
  const executionRunsClient = useReeRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation({
    mutationFn: ({ experimentName }: { experimentName: string }) =>
      executionRunsClient.startExperimentRun(resolvedReeId, experimentName),
    onSuccess: ({ reeId: startedReeId, run }) => {
      queryClient.setQueryData(queryKeys.stepRuns(startedReeId, run.runId), run);
    },
  });
}

export function useCancelReeRunMutation(reeId?: string) {
  const runtime = useReeRuntime();
  const executionRunsClient = useReeRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useMutation({
    mutationFn: async ({ runId }: { runId: string }) => {
      const status = await executionRunsClient.cancelReeRun(resolvedReeId, runId);
      return { runId, status };
    },
    onSuccess: async ({ runId }) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.stepRuns(resolvedReeId, runId),
      });
    },
  });
}
