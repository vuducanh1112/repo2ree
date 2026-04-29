import type { AutomationStepKey, AutomationStepParams, AutomationStepRunParams } from "../../types";

interface CancelTrackedRunArgs {
  key: string;
  cancelRun?: (runId: string) => Promise<unknown>;
}

interface CancelTrackedRunResult {
  ok: boolean;
  message?: string;
}

interface ExplorerRunSession {
  noteRunStarted(key: string, runId: string): void;
  noteRunFinished(key: string): void;
  getActiveRunId(key: string): string | undefined;
  mergeAutomationStepParams<K extends AutomationStepKey>(
    stepParams: AutomationStepParams,
    key: K,
    params: AutomationStepRunParams<K>,
  ): AutomationStepParams;
  cancelTrackedRun(args: CancelTrackedRunArgs): Promise<CancelTrackedRunResult>;
}

export function createWorkflowRunSession(): ExplorerRunSession {
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

    mergeAutomationStepParams(stepParams, key, params) {
      return {
        ...stepParams,
        [key]: { ...stepParams[key], ...params },
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
