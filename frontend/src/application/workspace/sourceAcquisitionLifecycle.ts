import type { LogLine } from "../../domain/ree/ReeTypes";
import type { WorkspaceResetPayload } from "../ports/repositoryTypes";
import { parseWorkspaceResetPayload } from "../ports/repositoryTypes";

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
  workspaceRepository: SourceWorkflowRunner;
  workflowRunRepository: SourceWorkflowPoller;
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
  workspaceRepository,
  workflowRunRepository,
  workspaceId,
  resetPayload,
  runParams,
  pollRun,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunSourceWorkspaceActionArgs): Promise<SourceWorkflowResult> {
  if (!runParams.mode) {
    await workspaceRepository.resetWorkspaceRequest(
      workspaceId,
      parseWorkspaceResetPayload(resetPayload, "git"),
    );
    return { status: "succeeded" };
  }

  const run = await workflowRunRepository.startWorkflowRun(workspaceId, "source", runParams);
  onRunStarted?.("source", run.runId);
  try {
    return await pollRun(workspaceId, run.runId, onUpdateLogs);
  } finally {
    onRunFinished?.("source");
  }
}
