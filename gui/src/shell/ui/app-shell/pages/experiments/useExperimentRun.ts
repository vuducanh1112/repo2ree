import type { LogLine } from "@core/ree/ReeTypes";
import type { ExperimentRunOutputs } from "@core/runs/ExperimentRun";
import type { ReeRunFailure } from "@core/runs/ReeRun";
import { isTerminalReeRunStatus, type ReeRunStatus } from "@core/runs/ReeRunStatus";
import { queryKeys } from "@shell/data/queryKeys";
import { useCancelReeRunMutation, useStartExperimentRunMutation } from "@shell/data/runs/mutations";
import { useReeRunLogsQuery, useReeRunQuery } from "@shell/data/runs/queries";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type RunState = {
  reeId: string;
  runId: string;
  status: ReeRunStatus;
  outputs: ExperimentRunOutputs | null;
  failure: ReeRunFailure | null;
  error: string | null;
  startedAt: string;
  logLines: LogLine[];
};

function mapExperimentOutputs(
  outputs: Record<string, unknown> | undefined,
): ExperimentRunOutputs | null {
  if (!outputs) return null;
  return {
    subjectName: String(outputs.subject_name ?? ""),
    exitCode: (outputs.exit_code as number | null) ?? null,
    verifyExitCode: outputs.verify_exit_code as number | null | undefined,
    verdict: outputs.verdict as "pass" | "fail" | undefined,
    experimentEnvironmentPath: outputs.experiment_environment_path as string | undefined,
  };
}

interface UseExperimentRunOptions {
  reeId: string;
  experimentName: string | null;
  onBeforeRun: () => Promise<void>;
}

interface ExperimentRunController {
  runState: RunState | null;
  isRunning: boolean;
  startRun: () => void;
  cancelRun: () => void;
}

interface RunTarget {
  reeId: string;
  runId: string;
  status: ReeRunStatus;
  startedAt: string;
}

export function useExperimentRun({
  reeId,
  experimentName,
  onBeforeRun,
}: UseExperimentRunOptions): ExperimentRunController {
  const queryClient = useQueryClient();
  const { mutateAsync: startExperimentRun } = useStartExperimentRunMutation(reeId);
  const { mutate: cancelReeRun } = useCancelReeRunMutation(reeId);
  const [target, setTarget] = useState<RunTarget | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [startingAt, setStartingAt] = useState<string | null>(null);

  // biome-ignore lint/correctness/useExhaustiveDependencies: experimentName drives the reset
  useEffect(() => {
    setTarget(null);
    setStartError(null);
    setStartingAt(null);
  }, [experimentName]);

  const runQuery = useReeRunQuery(target?.reeId, target?.runId);
  const logsQuery = useReeRunLogsQuery(target?.reeId, target?.runId);
  const refreshedRunId = useRef<string | null>(null);

  useEffect(() => {
    if (!target || !isTerminalReeRunStatus(runQuery.data?.status)) return;
    if (refreshedRunId.current === target.runId) return;
    refreshedRunId.current = target.runId;
    void queryClient.invalidateQueries({ queryKey: queryKeys.reeRuns(target.reeId) });
  }, [queryClient, runQuery.data?.status, target]);

  const startRun = useCallback(() => {
    if (!experimentName) return;
    setTarget(null);
    setStartError(null);
    setStartingAt(new Date().toISOString());
    void (async () => {
      try {
        await onBeforeRun();
        const { reeId: startedReeId, run } = await startExperimentRun({ experimentName });
        setTarget({
          reeId: startedReeId,
          runId: run.runId,
          status: run.status,
          startedAt: run.startedAt || run.createdAt || new Date().toISOString(),
        });
      } catch {
        setStartError("Failed to start run");
      } finally {
        setStartingAt(null);
      }
    })();
  }, [experimentName, onBeforeRun, startExperimentRun]);

  const runState = useMemo<RunState | null>(() => {
    if (startError) {
      return {
        reeId,
        runId: "",
        status: "failed",
        outputs: null,
        failure: null,
        error: startError,
        startedAt: new Date().toISOString(),
        logLines: [],
      };
    }
    if (!target) {
      if (!startingAt) return null;
      return {
        reeId,
        runId: "",
        status: "created",
        outputs: null,
        failure: null,
        error: null,
        startedAt: startingAt,
        logLines: [],
      };
    }
    const run = runQuery.data;
    const status = run?.status ?? target.status;
    const isTerminal = isTerminalReeRunStatus(status);
    return {
      reeId: target.reeId,
      runId: target.runId,
      status,
      outputs: isTerminal ? mapExperimentOutputs(run?.outputs) : null,
      failure: run?.failure ?? null,
      error: null,
      startedAt: target.startedAt,
      logLines: logsQuery.data?.lines ?? [],
    };
  }, [startError, startingAt, target, runQuery.data, logsQuery.data, reeId]);

  const isRunning = runState !== null && !isTerminalReeRunStatus(runState.status);

  const cancelRun = useCallback(() => {
    if (!target?.runId) return;
    cancelReeRun({ runId: target.runId });
  }, [cancelReeRun, target]);

  return { runState, isRunning, startRun, cancelRun };
}
