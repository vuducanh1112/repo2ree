import type {
  IWorkspaceService,
  LogLine,
  WorkflowRunRecord,
  WorkflowRunStatus,
} from "../../../../services/workspaceService";

interface PollWorkflowRunOptions {
  workspaceId: string;
  runId: string;
  maxIterations?: number;
}

interface PollWorkflowRunResult {
  status: WorkflowRunStatus;
  lines: LogLine[];
  ts: string;
}

const TERMINAL_STATUSES = new Set<WorkflowRunStatus>(["succeeded", "failed", "canceled"]);

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function resolvePollDelay(iteration: number): number {
  if (iteration < 10) return 1000;
  if (iteration < 30) return 2500;
  return 5000;
}

async function readAvailableLogs(
  workspaceService: IWorkspaceService,
  workspaceId: string,
  runId: string,
): Promise<LogLine[]> {
  if (!workspaceService.getWorkflowRunLogs) {
    return [];
  }

  const lines: LogLine[] = [];
  let cursor: string | undefined;
  for (let i = 0; i < 20; i += 1) {
    const chunk = await workspaceService.getWorkflowRunLogs(workspaceId, runId, cursor);
    lines.push(...chunk.lines);
    if (!chunk.hasMore || !chunk.nextCursor) {
      break;
    }
    cursor = chunk.nextCursor;
  }
  return lines;
}

function resolveRunTimestamp(run: WorkflowRunRecord): string {
  return run.finishedAt || run.startedAt || run.createdAt || new Date().toISOString();
}

export async function pollWorkflowRun(
  workspaceService: IWorkspaceService,
  options: PollWorkflowRunOptions,
): Promise<PollWorkflowRunResult> {
  if (!workspaceService.getWorkflowRun) {
    return {
      status: "failed",
      lines: [{ type: "err", msg: "Workflow polling is not supported by this service" }],
      ts: new Date().toISOString(),
    };
  }

  const maxIterations = options.maxIterations || 90;
  let latestRun = await workspaceService.getWorkflowRun(options.workspaceId, options.runId);

  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    if (TERMINAL_STATUSES.has(latestRun.status)) {
      const lines = await readAvailableLogs(workspaceService, options.workspaceId, options.runId);
      return {
        status: latestRun.status,
        lines,
        ts: resolveRunTimestamp(latestRun),
      };
    }

    await sleep(resolvePollDelay(iteration));
    latestRun = await workspaceService.getWorkflowRun(options.workspaceId, options.runId);
  }

  const lines = await readAvailableLogs(workspaceService, options.workspaceId, options.runId);
  return {
    status: latestRun.status,
    lines: [...lines, { type: "warn", msg: "Run still active after polling window ended" }],
    ts: resolveRunTimestamp(latestRun),
  };
}
