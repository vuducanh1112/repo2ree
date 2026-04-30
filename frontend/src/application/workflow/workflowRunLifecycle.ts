import type { LogLine } from "../../domain/ree/ReeTypes";
import type { GenericWorkflowParams } from "./WorkflowStepTypes";

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
  startWorkflowRun: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<WorkflowRunRecord>;
  request: {
    key: string;
    scriptKey: string;
    params: GenericWorkflowParams;
  };
  pollRun: (
    runId: string,
    onUpdate?: (update: WorkflowRunUpdate) => void,
  ) => Promise<WorkflowRunResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
  onUpdateLogs?: (update: WorkflowRunUpdate) => void;
}

export async function runWorkflowLifecycle({
  startWorkflowRun,
  request,
  pollRun,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunWorkflowLifecycleArgs): Promise<WorkflowRunResult> {
  let runId: string | null = null;
  try {
    const run = await startWorkflowRun(request.scriptKey, request.params);
    runId = run.runId;
    onRunStarted?.(request.key, run.runId);
    return await pollRun(run.runId, onUpdateLogs);
  } finally {
    if (runId) {
      onRunFinished?.(request.key);
    }
  }
}
