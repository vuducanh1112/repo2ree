import type {
  ReeAssemblyOperationKey,
  ReeAssemblyOperationParams,
  ReeAssemblyRunParams,
} from "./assemblyTypes";

interface CancelTrackedRunArgs {
  key: string;
  cancelRun?: (runId: string) => Promise<unknown>;
}

interface CancelTrackedRunResult {
  ok: boolean;
  message?: string;
}

interface AssemblyRunSession {
  noteRunStarted(key: string, runId: string): void;
  noteRunFinished(key: string): void;
  getActiveRunId(key: string): string | undefined;
  mergeAssemblyOperationParams<K extends ReeAssemblyOperationKey>(
    stepParams: ReeAssemblyOperationParams,
    key: K,
    params: ReeAssemblyRunParams<K>,
  ): ReeAssemblyOperationParams;
  cancelTrackedRun(args: CancelTrackedRunArgs): Promise<CancelTrackedRunResult>;
}

export function createAssemblyRunSession(): AssemblyRunSession {
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

    mergeAssemblyOperationParams(stepParams, key, params) {
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
