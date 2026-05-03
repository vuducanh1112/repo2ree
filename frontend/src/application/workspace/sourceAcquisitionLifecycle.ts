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
  workspaceClient: SourceWorkflowRunner;
  workflowRunClient: SourceWorkflowPoller;
  workspaceId: string;
  resetPayload: string;
  runParams: Record<string, string | boolean | number | null | undefined>;
  pollRun: (
    workspaceId: string,
    runId: string,
    onUpdate?: (update: SourceWorkflowUpdate) => void,
  ) => Promise<SourceWorkflowResult>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
  onUpdateLogs?: (update: SourceWorkflowUpdate) => void;
}

export async function runSourceWorkspaceAction({
  workspaceClient,
  workflowRunClient,
  workspaceId,
  resetPayload,
  runParams,
  pollRun,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunSourceWorkspaceActionArgs): Promise<SourceWorkflowResult> {
  if (!runParams.mode) {
    await workspaceClient.resetWorkspaceRequest(
      workspaceId,
      parseWorkspaceResetPayload(resetPayload, "git"),
    );
    return { status: "succeeded" };
  }

  const run = await workflowRunClient.startWorkflowRun(workspaceId, "source", runParams);
  onRunStarted?.("source", run.runId);
  try {
    return await pollRun(workspaceId, run.runId, onUpdateLogs);
  } finally {
    onRunFinished?.("source");
  }
}
