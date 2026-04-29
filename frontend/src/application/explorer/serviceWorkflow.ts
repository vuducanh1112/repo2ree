import type { LogLine } from "../../types";
import type { GenericServiceParams } from "../../types/services";

type ServiceWorkflowStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

interface ServiceWorkflowRunRecord {
  runId: string;
}

interface ServiceWorkflowUpdate {
  lines: LogLine[];
  ts: string;
}

interface ServiceWorkflowResult {
  status: ServiceWorkflowStatus;
  lines: LogLine[];
  ts: string;
}

interface RunServiceWorkflowArgs {
  startWorkflowRun?: (
    key: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<ServiceWorkflowRunRecord>;
  key: string;
  runParams: GenericServiceParams;
  pollRun: (
    runId: string,
    onUpdate?: (update: ServiceWorkflowUpdate) => void,
  ) => Promise<ServiceWorkflowResult>;
  createMockResult: () => Promise<ServiceWorkflowResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
  onUpdateLogs?: (update: ServiceWorkflowUpdate) => void;
}

export async function runServiceWorkflow({
  startWorkflowRun,
  key,
  runParams,
  pollRun,
  createMockResult,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunServiceWorkflowArgs): Promise<ServiceWorkflowResult> {
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
