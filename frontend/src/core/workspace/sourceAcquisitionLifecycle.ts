import type { LogLine } from "../../core/ree/ReeTypes";
import type { WorkspaceResetPayload } from "../../core/workspace/WorkspaceReset";
import { parseWorkspaceResetPayload } from "../../core/workspace/WorkspaceReset";

type SourceExecutionStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

interface SourceReeRunRecord {
  runId: string;
}

interface SourceExecutionUpdate {
  lines: LogLine[];
  ts: string;
}

interface SourceExecutionResult {
  runId?: string;
  status: SourceExecutionStatus;
}

interface SourceReeRunner {
  resetWorkspaceRequest: (id: string, payload: WorkspaceResetPayload) => Promise<void>;
}

interface SourceExecutionPoller {
  startReeRun: (
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<SourceReeRunRecord>;
}

interface RunSourceWorkspaceActionArgs {
  reeClient: SourceReeRunner;
  executionRunClient: SourceExecutionPoller;
  reeId: string;
  resetPayload: string;
  runParams: Record<string, string | boolean | number | null | undefined>;
  pollRun: (
    reeId: string,
    runId: string,
    onUpdate?: (update: SourceExecutionUpdate) => void,
  ) => Promise<SourceExecutionResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string, runId: string) => void;
  onUpdateLogs?: (update: SourceExecutionUpdate) => void;
}

export async function runSourceWorkspaceAction({
  reeClient,
  executionRunClient,
  reeId,
  resetPayload,
  runParams,
  pollRun,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunSourceWorkspaceActionArgs): Promise<SourceExecutionResult> {
  if (!runParams.mode) {
    await reeClient.resetWorkspaceRequest(reeId, parseWorkspaceResetPayload(resetPayload, "git"));
    return { status: "succeeded" };
  }

  const run = await executionRunClient.startReeRun(reeId, "source", runParams);
  onRunStarted?.("source", run.runId);
  try {
    const result = await pollRun(reeId, run.runId, onUpdateLogs);
    return { ...result, runId: run.runId };
  } finally {
    onRunFinished?.("source", run.runId);
  }
}
