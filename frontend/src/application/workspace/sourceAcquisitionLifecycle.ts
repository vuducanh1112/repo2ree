import type { LogLine } from "../../domain/ree/ReeTypes";
import type { WorkspaceResetPayload } from "../../domain/workspace/WorkspaceReset";
import { parseWorkspaceResetPayload } from "../../domain/workspace/WorkspaceReset";

type SourceExecutionStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

interface SourceExecutionRunRecord {
  runId: string;
}

interface SourceExecutionUpdate {
  lines: LogLine[];
  ts: string;
}

interface SourceExecutionResult {
  status: SourceExecutionStatus;
}

interface SourceExecutionRunner {
  resetWorkspaceRequest: (id: string, payload: WorkspaceResetPayload) => Promise<void>;
}

interface SourceExecutionPoller {
  startExecutionRun: (
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<SourceExecutionRunRecord>;
}

interface RunSourceWorkspaceActionArgs {
  reeClient: SourceExecutionRunner;
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
  onRunFinished?: (key: string) => void;
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

  const run = await executionRunClient.startExecutionRun(reeId, "source", runParams);
  onRunStarted?.("source", run.runId);
  try {
    return await pollRun(reeId, run.runId, onUpdateLogs);
  } finally {
    onRunFinished?.("source");
  }
}
