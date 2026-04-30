import type { LogLine } from "../../domain/ree/ReeTypes";

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
  resetWorkspace(id: string, newSource: string): Promise<void>;
  startWorkflowRun?: (
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<SourceWorkflowRunRecord>;
  getWorkflowRun?: (id: string, runId: string) => Promise<{ status: SourceWorkflowStatus }>;
}

interface RunSourceWorkspaceActionArgs {
  workspaceService: SourceWorkflowRunner;
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
  workspaceService,
  workspaceId,
  resetPayload,
  runParams,
  pollRun,
  onRunStarted,
  onRunFinished,
  onUpdateLogs,
}: RunSourceWorkspaceActionArgs): Promise<SourceWorkflowResult> {
  if (!workspaceService.startWorkflowRun || !workspaceService.getWorkflowRun) {
    await workspaceService.resetWorkspace(workspaceId, resetPayload);
    return { status: "succeeded" };
  }

  const run = await workspaceService.startWorkflowRun(workspaceId, "source", runParams);
  onRunStarted?.("source", run.runId);
  try {
    return await pollRun(workspaceId, run.runId, onUpdateLogs);
  } finally {
    onRunFinished?.("source");
  }
}
