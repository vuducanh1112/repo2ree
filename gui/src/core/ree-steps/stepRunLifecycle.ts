import type { LogLine } from "../ree/ReeTypes";
import type { ReeRunStatus } from "../runs/ReeRunStatus";

/** The values a run request forwards to the backend, untouched. */
type ReeRunParams = Record<string, string | boolean | number | null | undefined>;

interface ReeRunRecord {
  runId: string;
}

/** A log snapshot handed to the caller each time the poller sees progress. */
export interface ReeRunUpdate {
  lines: LogLine[];
  ts: string;
}

/** What observing a run to completion yields. */
export interface ReeRunPollResult {
  status: ReeRunStatus;
  lines: LogLine[];
  ts: string;
}

interface ReeRunResult extends ReeRunPollResult {
  runId: string;
}

interface RunExecutionLifecycleArgs {
  startReeRun: (key: string, params?: ReeRunParams) => Promise<ReeRunRecord>;
  request: {
    key: string;
    scriptKey: string;
    params: ReeRunParams;
  };
  pollRun: (runId: string, onUpdate?: (update: ReeRunUpdate) => void) => Promise<ReeRunPollResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string, runId: string) => void;
  onUpdateLogs?: (update: ReeRunUpdate) => void;
}

/**
 * Start a run, observe it to completion, and report it started/finished exactly
 * once. Every run the app drives — steps, source acquisition — goes through
 * here, so the started/finished bookkeeping (in particular: `finally`, so a
 * poller that throws still releases the run) is written once.
 */
export async function runExecutionLifecycle({
  startReeRun,
  request,
  pollRun,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunExecutionLifecycleArgs): Promise<ReeRunResult> {
  let runId: string | null = null;
  try {
    const run = await startReeRun(request.scriptKey, request.params);
    runId = run.runId;
    onRunStarted?.(request.key, run.runId);
    const result = await pollRun(run.runId, onUpdateLogs);
    return { ...result, runId: run.runId };
  } finally {
    if (runId) {
      onRunFinished?.(request.key, runId);
    }
  }
}
