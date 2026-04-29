import type {
  WorkflowServiceKey,
  WorkflowServiceParams,
  WorkflowServiceRunParams,
} from "../../types";

interface CancelTrackedWorkflowRunArgs {
  key: string;
  cancelRun?: (runId: string) => Promise<unknown>;
}

interface CancelTrackedWorkflowRunResult {
  ok: boolean;
  message?: string;
}

interface ExplorerWorkflowSession {
  noteRunStarted(key: string, runId: string): void;
  noteRunFinished(key: string): void;
  getActiveRunId(key: string): string | undefined;
  mergeWorkflowParams<K extends WorkflowServiceKey>(
    serviceParams: WorkflowServiceParams,
    key: K,
    params: WorkflowServiceRunParams<K>,
  ): WorkflowServiceParams;
  cancelTrackedRun(args: CancelTrackedWorkflowRunArgs): Promise<CancelTrackedWorkflowRunResult>;
}

export function createExplorerWorkflowSession(): ExplorerWorkflowSession {
  const activeRunIds: Record<string, string> = {};

  return {
    noteRunStarted(key, runId) {
      activeRunIds[key] = runId;
    },

    noteRunFinished(key) {
      delete activeRunIds[key];
    },

    getActiveRunId(key) {
      return activeRunIds[key];
    },

    mergeWorkflowParams(serviceParams, key, params) {
      return {
        ...serviceParams,
        [key]: { ...serviceParams[key], ...params },
      };
    },

    async cancelTrackedRun({ key, cancelRun }) {
      const runId = activeRunIds[key];
      if (!runId || !cancelRun) {
        return { ok: false };
      }

      try {
        await cancelRun(runId);
        return {
          ok: true,
          message: `Cancel requested for ${key}`,
        };
      } catch (error) {
        return {
          ok: false,
          message:
            error instanceof Error
              ? `Failed to cancel ${key}: ${error.message}`
              : `Failed to cancel ${key}`,
        };
      }
    },
  };
}
