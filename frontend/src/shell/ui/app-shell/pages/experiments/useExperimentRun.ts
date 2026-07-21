import type { LogLine } from "@core/ree/ReeTypes";
import type { ExperimentRunOutputs } from "@core/runs/ExperimentRun";
import type { ReeRunFailure } from "@core/runs/ReeRun";
import type { ReeRunStatus } from "@core/runs/ReeRunStatus";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useReeRunLogsQuery, useReeRunQuery } from "@shell/data/runs/queries";
import { useCallback, useEffect, useMemo, useState } from "react";

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

export const TERMINAL_STATUSES: ReeRunStatus[] = ["succeeded", "failed", "canceled"];

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
  const { runsApi, ensureReeId } = useApiRuntime();
  const [target, setTarget] = useState<RunTarget | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  // Switching experiments (or returning to the catalog) abandons the previous
  // run's result — each experiment shows only its own run. experimentName is the
  // reset trigger, not read in the body.
  // biome-ignore lint/correctness/useExhaustiveDependencies: experimentName drives the reset
  useEffect(() => {
    setTarget(null);
    setStartError(null);
  }, [experimentName]);

  const runQuery = useReeRunQuery(target?.reeId, target?.runId);
  const logsQuery = useReeRunLogsQuery(target?.reeId, target?.runId);

  const startRun = useCallback(() => {
    if (!experimentName) return;
    setTarget(null);
    setStartError(null);
    void (async () => {
      try {
        // Flush any pending debounced draft edits (e.g. the script the user
        // just saved) before running — the backend validates the run against
        // the persisted draft, so a stale draft would 400 the run.
        await onBeforeRun();
        const resolvedReeId = await ensureReeId(reeId);
        const run = await runsApi.createExperimentRun(resolvedReeId, experimentName, {});
        setTarget({
          reeId: resolvedReeId,
          runId: run.run_id,
          status: run.status,
          startedAt: run.started_at || run.created_at || new Date().toISOString(),
        });
      } catch {
        setStartError("Failed to start run");
      }
    })();
  }, [ensureReeId, reeId, experimentName, runsApi, onBeforeRun]);

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
    if (!target) return null;
    const run = runQuery.data;
    const status = run?.status ?? target.status;
    const isTerminal = TERMINAL_STATUSES.includes(status);
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
  }, [startError, target, runQuery.data, logsQuery.data, reeId]);

  const isRunning = runState !== null && !TERMINAL_STATUSES.includes(runState.status);

  return { runState, isRunning, startRun };
}
