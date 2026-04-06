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
  onUpdate?: (update: PollWorkflowRunResult) => void;
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
  cursor?: string,
): Promise<LogLine[]> {
  if (!workspaceService.getWorkflowRunLogs) {
    return [];
  }

  const lines: LogLine[] = [];
  let nextCursor = cursor;
  for (let i = 0; i < 20; i += 1) {
    const chunk = await workspaceService.getWorkflowRunLogs(workspaceId, runId, nextCursor);
    lines.push(...chunk.lines);
    if (!chunk.hasMore && !chunk.lines.length) {
      break;
    }
    nextCursor = chunk.nextCursor || String((Number(nextCursor || "0") || 0) + chunk.lines.length);
    if (!chunk.hasMore) {
      break;
    }
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
  let logCursor: string | undefined;
  let fetchedLogCount = 0;
  let aggregatedLines: LogLine[] = [];

  const pullLogs = async (): Promise<void> => {
    if (!workspaceService.getWorkflowRunLogs) return;
    const requestCursor = logCursor || String(fetchedLogCount);
    const chunk = await workspaceService.getWorkflowRunLogs(
      options.workspaceId,
      options.runId,
      requestCursor,
    );
    aggregatedLines = [...aggregatedLines, ...chunk.lines];
    fetchedLogCount += chunk.lines.length;
    logCursor = chunk.nextCursor || String(fetchedLogCount);
  };

  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    await pullLogs();
    const snapshot: PollWorkflowRunResult = {
      status: latestRun.status,
      lines: aggregatedLines,
      ts: resolveRunTimestamp(latestRun),
    };
    options.onUpdate?.(snapshot);

    if (TERMINAL_STATUSES.has(latestRun.status)) {
      const lines = await readAvailableLogs(
        workspaceService,
        options.workspaceId,
        options.runId,
        logCursor,
      );
      aggregatedLines = [...aggregatedLines, ...lines];
      return {
        status: latestRun.status,
        lines: aggregatedLines,
        ts: resolveRunTimestamp(latestRun),
      };
    }

    await sleep(resolvePollDelay(iteration));
    latestRun = await workspaceService.getWorkflowRun(options.workspaceId, options.runId);
  }

  const lines = await readAvailableLogs(
    workspaceService,
    options.workspaceId,
    options.runId,
    logCursor,
  );
  aggregatedLines = [...aggregatedLines, ...lines];
  return {
    status: latestRun.status,
    lines: [
      ...aggregatedLines,
      { type: "warn", msg: "Run still active after polling window ended" },
    ],
    ts: resolveRunTimestamp(latestRun),
  };
}
