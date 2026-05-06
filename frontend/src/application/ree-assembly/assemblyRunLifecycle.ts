import type { LogLine } from "../../core/ree/ReeTypes";
import type { GenericReeAssemblyParams } from "./assemblyStepTypes";

type ExecutionRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

interface ExecutionRunRecord {
  runId: string;
}

interface ExecutionRunUpdate {
  lines: LogLine[];
  ts: string;
}

interface ExecutionRunResult {
  status: ExecutionRunStatus;
  lines: LogLine[];
  ts: string;
}

interface RunExecutionLifecycleArgs {
  startExecutionRun: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<ExecutionRunRecord>;
  request: {
    key: string;
    scriptKey: string;
    params: GenericReeAssemblyParams;
  };
  pollRun: (
    runId: string,
    onUpdate?: (update: ExecutionRunUpdate) => void,
  ) => Promise<ExecutionRunResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
  onUpdateLogs?: (update: ExecutionRunUpdate) => void;
}

export async function runExecutionLifecycle({
  startExecutionRun,
  request,
  pollRun,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunExecutionLifecycleArgs): Promise<ExecutionRunResult> {
  let runId: string | null = null;
  try {
    const run = await startExecutionRun(request.scriptKey, request.params);
    runId = run.runId;
    onRunStarted?.(request.key, run.runId);
    return await pollRun(run.runId, onUpdateLogs);
  } finally {
    if (runId) {
      onRunFinished?.(request.key);
    }
  }
}
