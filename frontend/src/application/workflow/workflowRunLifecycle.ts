import type { LogLine } from "../../domain/ree/ReeTypes";
import type { GenericServiceParams } from "./WorkflowStepTypes";

type WorkflowRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

interface WorkflowRunRecord {
  runId: string;
}

interface WorkflowRunUpdate {
  lines: LogLine[];
  ts: string;
}

interface WorkflowRunResult {
  status: WorkflowRunStatus;
  lines: LogLine[];
  ts: string;
}

interface RunWorkflowLifecycleArgs {
  startWorkflowRun?: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<WorkflowRunRecord>;
  key: string;
  runParams: GenericServiceParams;
  pollRun: (
    runId: string,
    onUpdate?: (update: WorkflowRunUpdate) => void,
  ) => Promise<WorkflowRunResult>;
  createMockResult: () => Promise<WorkflowRunResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
  onUpdateLogs?: (update: WorkflowRunUpdate) => void;
}

export async function runWorkflowLifecycle({
  startWorkflowRun,
  key,
  runParams,
  pollRun,
  createMockResult,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunWorkflowLifecycleArgs): Promise<WorkflowRunResult> {
  if (!startWorkflowRun) {
    return createMockResult();
  }

  let runId: string | null = null;
  try {
    const run = await startWorkflowRun(key, runParams);
    runId = run.runId;
    onRunStarted?.(key, run.runId);
    return await pollRun(run.runId, onUpdateLogs);
  } finally {
    if (runId) {
      onRunFinished?.(key);
    }
  }
}
