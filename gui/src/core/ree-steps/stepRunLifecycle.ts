import type { ReeRunOperation } from "@core/generated/vocabulary";
import type { LogLine } from "../ree/ReeTypes";
import type { ReeRunStatus } from "../runs/ReeRunStatus";

type ReeRunParams = Record<string, string | boolean | number | null | undefined>;

interface ReeRunRecord {
  runId: string;
}

export interface ReeRunUpdate {
  lines: LogLine[];
  ts: string;
}

export interface ReeRunPollResult {
  status: ReeRunStatus;
  lines: LogLine[];
  ts: string;
}

interface ReeRunResult extends ReeRunPollResult {
  runId: string;
}

interface RunExecutionLifecycleArgs {
  startReeRun: (operation: ReeRunOperation, params?: ReeRunParams) => Promise<ReeRunRecord>;
  request: {
    key: string;
    scriptKey: ReeRunOperation;
    params: ReeRunParams;
  };
  pollRun: (runId: string, onUpdate?: (update: ReeRunUpdate) => void) => Promise<ReeRunPollResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string, runId: string) => void;
  onUpdateLogs?: (update: ReeRunUpdate) => void;
}

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
