import type { ExecutionRunStatus } from "@core/execution/ExecutionRunStatus";
import type { ExperimentRunOutputs } from "@core/execution/ExperimentRun";
import type { LogLine } from "@core/ree/ReeTypes";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useExecutionRunsClient } from "@shell/data/execution-runs/client";
import { useCallback, useEffect, useRef, useState } from "react";

export type RunState = {
  reeId: string;
  runId: string;
  mode: "verify" | "snapshot";
  status: ExecutionRunStatus;
  outputs: ExperimentRunOutputs | null;
  error: string | null;
  startedAt: string;
  logLines: LogLine[];
  logCursor: string | undefined;
};

export const TERMINAL_STATUSES: ExecutionRunStatus[] = ["succeeded", "failed", "canceled"];

const MAX_RUN_LOG_LINES = 2000;

function appendCappedLogLines(existing: LogLine[], incoming: LogLine[]): LogLine[] {
  if (incoming.length === 0) return existing;
  const merged = existing.concat(incoming);
  if (merged.length <= MAX_RUN_LOG_LINES) return merged;
  return merged.slice(merged.length - MAX_RUN_LOG_LINES);
}

interface UseExperimentRunOptions {
  reeId: string;
  /** The experiment being viewed, or null when none is selected. */
  experimentName: string | null;
  onSnapshotComplete: () => Promise<void>;
  onBeforeRun: () => Promise<void>;
}

interface ExperimentRunController {
  runState: RunState | null;
  isRunning: boolean;
  startRun: (mode: "verify" | "snapshot") => void;
}

// Owns running/snapshotting a single experiment and polling the run to
// completion. Hoisted out of the detail view so the page header can drive the
// Run/Snapshot controls while the body still renders the result/log panel from
// the same runState.
export function useExperimentRun({
  reeId,
  experimentName,
  onSnapshotComplete,
  onBeforeRun,
}: UseExperimentRunOptions): ExperimentRunController {
  const { runsApi, ensureReeId } = useApiRuntime();
  const executionRunsClient = useExecutionRunsClient();
  const [runState, setRunState] = useState<RunState | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Switching experiments (or returning to the catalog) abandons the previous
  // run's result — each experiment shows only its own run. experimentName is the
  // reset trigger, not read in the body.
  // biome-ignore lint/correctness/useExhaustiveDependencies: experimentName drives the reset
  useEffect(() => {
    setRunState(null);
    stopPolling();
  }, [experimentName, stopPolling]);

  const fetchLogsOnce = useCallback(
    async (reeId: string, runId: string, cursor: string | undefined) => {
      let nextCursor = cursor;
      const collected: LogLine[] = [];
      for (let page = 0; page < 20; page += 1) {
        const chunk = await executionRunsClient.getExecutionRunLogs(reeId, runId, nextCursor);
        collected.push(...chunk.lines);
        nextCursor = chunk.nextCursor || nextCursor;
        if (!chunk.hasMore) break;
        if (!chunk.nextCursor) break;
      }
      return { lines: collected, cursor: nextCursor };
    },
    [executionRunsClient],
  );

  useEffect(() => {
    if (!runState || TERMINAL_STATUSES.includes(runState.status)) return;
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const [run, logChunk] = await Promise.all([
          runsApi.getRun(runState.reeId, runState.runId),
          fetchLogsOnce(runState.reeId, runState.runId, runState.logCursor),
        ]);
        const isTerminal = TERMINAL_STATUSES.includes(run.status);
        const outputs = isTerminal
          ? ((run.outputs as unknown as ExperimentRunOutputs | null) ?? null)
          : null;
        setRunState((prev) =>
          prev
            ? {
                ...prev,
                status: run.status,
                outputs: outputs ?? prev.outputs,
                logLines: appendCappedLogLines(prev.logLines, logChunk.lines),
                logCursor: logChunk.cursor ?? prev.logCursor,
              }
            : prev,
        );
        if (isTerminal) {
          stopPolling();
          if (outputs?.snapshotApplied) {
            await onSnapshotComplete();
          }
        }
      } catch {
        stopPolling();
        setRunState((prev) => (prev ? { ...prev, error: "Failed to poll run status" } : prev));
      }
    }, 1500);
    return stopPolling;
  }, [runState, runsApi, stopPolling, onSnapshotComplete, fetchLogsOnce]);

  const startRun = useCallback(
    (mode: "verify" | "snapshot") => {
      if (!experimentName) return;
      setRunState(null);
      void (async () => {
        try {
          // Flush any pending debounced draft edits (e.g. the command the user
          // just typed) before running — the backend validates the run against
          // the persisted draft, so a stale draft would 400 the run.
          await onBeforeRun();
          const resolvedReeId = await ensureReeId(reeId);
          const run = await runsApi.createExperimentRun(resolvedReeId, experimentName, { mode });
          setRunState({
            reeId: resolvedReeId,
            runId: run.runId,
            mode,
            status: run.status,
            outputs: null,
            error: null,
            startedAt: run.startedAt || run.createdAt || new Date().toISOString(),
            logLines: [],
            logCursor: undefined,
          });
        } catch {
          setRunState({
            reeId,
            runId: "",
            mode,
            status: "failed",
            outputs: null,
            error: "Failed to start run",
            startedAt: new Date().toISOString(),
            logLines: [],
            logCursor: undefined,
          });
        }
      })();
    },
    [ensureReeId, reeId, experimentName, runsApi, onBeforeRun],
  );

  const isRunning = runState !== null && !TERMINAL_STATUSES.includes(runState.status);

  return { runState, isRunning, startRun };
}
