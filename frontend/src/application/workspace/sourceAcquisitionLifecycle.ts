import type { LogLine } from "../../domain/ree/ReeTypes";
import type { WorkspaceResetPayload } from "../../domain/workspace/WorkspaceReset";
import { parseWorkspaceResetPayload } from "../../domain/workspace/WorkspaceReset";

type SourceWorkflowStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

interface SourceWorkflowRunRecord {
  runId: string;
}

interface SourceWorkflowUpdate {
  lines: LogLine[];
  ts: string;
}

interface SourceWorkflowResult {
  status: SourceWorkflowStatus;
}

interface SourceWorkflowRunner {
  resetWorkspaceRequest: (id: string, payload: WorkspaceResetPayload) => Promise<void>;
}

interface SourceWorkflowPoller {
  startWorkflowRun: (
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<SourceWorkflowRunRecord>;
}

interface RunSourceWorkspaceActionArgs {
  reeClient: SourceWorkflowRunner;
  workflowRunClient: SourceWorkflowPoller;
  reeId: string;
  resetPayload: string;
  runParams: Record<string, string | boolean | number | null | undefined>;
  pollRun: (
    reeId: string,
    runId: string,
    onUpdate?: (update: SourceWorkflowUpdate) => void,
  ) => Promise<SourceWorkflowResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
  onUpdateLogs?: (update: SourceWorkflowUpdate) => void;
}

export async function runSourceWorkspaceAction({
  reeClient,
  workflowRunClient,
  reeId,
  resetPayload,
  runParams,
  pollRun,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunSourceWorkspaceActionArgs): Promise<SourceWorkflowResult> {
  if (!runParams.mode) {
    await reeClient.resetWorkspaceRequest(reeId, parseWorkspaceResetPayload(resetPayload, "git"));
    return { status: "succeeded" };
  }

  const run = await workflowRunClient.startWorkflowRun(reeId, "source", runParams);
  onRunStarted?.("source", run.runId);
  try {
    return await pollRun(reeId, run.runId, onUpdateLogs);
  } finally {
    onRunFinished?.("source");
  }
}
