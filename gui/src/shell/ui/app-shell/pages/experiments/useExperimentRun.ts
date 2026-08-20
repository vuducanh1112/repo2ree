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
  // The typed reason a failed run did not succeed, when the backend recorded
  // one. Distinct from `error`, which is a client-side start failure.
  failure: ReeRunFailure | null;
  error: string | null;
  startedAt: string;
  logLines: LogLine[];
};

// The one experiment-specific mapping: the run's opaque outputs record narrowed
// to the exit codes and verdict this surface renders. Everything else (fetch,
// poll cadence, terminal detection, typed failure, log pagination) is the shared
// run stack — this hook must not re-implement it.
function mapExperimentOutputs(
  outputs: Record<string, unknown> | undefined,
): ExperimentRunOutputs | null {
  if (!outputs) return null;
  return {
    subjectName: String(outputs.subject_name ?? ""),
    exitCode: (outputs.exit_code as number | null) ?? null,
    verifyExitCode: outputs.verify_exit_code as number | null | undefined,
    verdict: outputs.verdict as "pass" | "fail" | undefined,
    runtimePath: outputs.runtime_path as string | undefined,
  };
}

interface UseExperimentRunOptions {
  reeId: string;
  /** The experiment being viewed, or null when none is selected. */
  experimentName: string | null;
  onBeforeRun: () => Promise<void>;
}

interface ExperimentRunController {
  runState: RunState | null;
  isRunning: boolean;
  startRun: () => void;
  /** Cancel the run in flight. No-op before the backend has handed one back. */
  cancelRun: () => void;
}

/** The run we started and are now observing, pinned so a later query resolution
 * keeps rendering against the same run rather than a stale one. */
interface RunTarget {
  reeId: string;
  runId: string;
  status: ReeRunStatus;
  startedAt: string;
}

// Owns running a single experiment and observing it to completion. Hoisted out
// of the detail view so the page header can drive the Run control while the body
// still renders the result/log panel from the same runState. Observation rides
// the shared run-query stack (useReeRunQuery/useReeRunLogsQuery) — the only bit
// that is experiment-specific is narrowing the run's outputs.
export function useExperimentRun({
  reeId,
  experimentName,
  onBeforeRun,
}: UseExperimentRunOptions): ExperimentRunController {
  const queryClient = useQueryClient();
  // Destructured: react-query keeps these callbacks stable across renders while
  // the mutation object itself is new each time, so the handlers below stay
  // memoized.
  const { mutateAsync: startExperimentRun } = useStartExperimentRunMutation(reeId);
  const { mutate: cancelReeRun } = useCancelReeRunMutation(reeId);
  const [target, setTarget] = useState<RunTarget | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  // When the click happened, for the window before the backend has a run to
  // observe. Set synchronously so the control and the result panel react on the
  // click's own frame rather than after the start round-trip.
  const [startingAt, setStartingAt] = useState<string | null>(null);

  // Switching experiments (or returning to the catalog) abandons the previous
  // run's result — each experiment shows only its own run. experimentName is the
  // reset trigger, not read in the body.
  // biome-ignore lint/correctness/useExhaustiveDependencies: experimentName drives the reset
  useEffect(() => {
    setTarget(null);
    setStartError(null);
    setStartingAt(null);
  }, [experimentName]);

  const runQuery = useReeRunQuery(target?.reeId, target?.runId);
  const logsQuery = useReeRunLogsQuery(target?.reeId, target?.runId);
  const refreshedRunId = useRef<string | null>(null);

  // Experiment execution does not use the generic step gateway, whose terminal
  // path refreshes the REE document. Refresh it here once so the receipt filed
  // by a completed experiment appears on the canvas without a remount.
  useEffect(() => {
    if (!target || !isTerminalReeRunStatus(runQuery.data?.status)) return;
    if (refreshedRunId.current === target.runId) return;
    refreshedRunId.current = target.runId;
    void queryClient.invalidateQueries({ queryKey: queryKeys.ree(target.reeId) });
  }, [queryClient, runQuery.data?.status, target]);

  const startRun = useCallback(() => {
    if (!experimentName) return;
    setTarget(null);
    setStartError(null);
    // Before any await: flushing the draft and creating the run together take
    // seconds, and until one of them lands there is no run to observe. Marking
    // the start here is what makes the button and log panel respond on click.
    setStartingAt(new Date().toISOString());
    void (async () => {
      try {
        // Flush any pending debounced draft edits (e.g. the script the user
        // just saved) before running — the backend validates the run against
        // the persisted draft, so a stale draft would 400 the run.
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
    // A start that never produced a run: a client-side failure with no backend
    // run to observe, surfaced on its own.
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
    // The start is in flight: report the run as created so the surface shows it
    // beginning. There is no run id yet, so nothing is polled and no logs exist
    // — the real target replaces this the moment the backend hands one back.
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
