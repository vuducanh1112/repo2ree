import type { WorkspaceEditorClock } from "../../../../application/workspace/workspaceEditorPorts";
import type {
  LogLine,
  WorkflowRunRecord,
  WorkflowRunStatus,
  WorkspaceGateway,
} from "../../../../workspace/WorkspaceGateway";

interface PollWorkflowRunOptions {
  workspaceId: string;
  runId: string;
  maxIterations?: number;
  onUpdate?: (update: PollWorkflowRunResult) => void;
  clock: WorkspaceEditorClock;
  sleep: (ms: number) => Promise<void>;
}

interface PollWorkflowRunResult {
  status: WorkflowRunStatus;
  lines: LogLine[];
  ts: string;
}

const TERMINAL_STATUSES = new Set<WorkflowRunStatus>(["succeeded", "failed", "canceled"]);
const MAX_LOG_LINES = 2000;
const MAX_LOG_MESSAGE_CHARS = 4000;

function resolvePollDelay(iteration: number): number {
  if (iteration < 10) return 1000;
  if (iteration < 30) return 2500;
  return 5000;
}

function sanitizeLine(line: LogLine): LogLine {
  if (line.msg.length <= MAX_LOG_MESSAGE_CHARS) return line;
  return {
    ...line,
    msg: `${line.msg.slice(0, MAX_LOG_MESSAGE_CHARS)}… [truncated]`,
  };
}

function mergeCappedLines(existing: LogLine[], incoming: LogLine[]): LogLine[] {
  if (incoming.length === 0) return existing;
  const merged = [...existing, ...incoming.map(sanitizeLine)];
  if (merged.length <= MAX_LOG_LINES) return merged;
  return merged.slice(merged.length - MAX_LOG_LINES);
}

async function readAvailableLogs(
  workspaceService: WorkspaceGateway,
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
    lines.push(...chunk.lines.map(sanitizeLine));
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

function resolveRunTimestamp(run: WorkflowRunRecord, clock: WorkspaceEditorClock): string {
  return run.finishedAt || run.startedAt || run.createdAt || clock.nowIso();
}

export async function pollWorkflowRun(
  workspaceService: WorkspaceGateway,
  options: PollWorkflowRunOptions,
): Promise<PollWorkflowRunResult> {
  if (!workspaceService.getWorkflowRun) {
    return {
      status: "failed",
      lines: [{ type: "err", msg: "Workflow polling is not supported by this service" }],
      ts: options.clock.nowIso(),
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
    aggregatedLines = mergeCappedLines(aggregatedLines, chunk.lines);
    fetchedLogCount += chunk.lines.length;
    logCursor = chunk.nextCursor || String(fetchedLogCount);
  };

  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    await pullLogs();
    const snapshot: PollWorkflowRunResult = {
      status: latestRun.status,
      lines: aggregatedLines,
      ts: resolveRunTimestamp(latestRun, options.clock),
    };
    options.onUpdate?.(snapshot);

    if (TERMINAL_STATUSES.has(latestRun.status)) {
      const lines = await readAvailableLogs(
        workspaceService,
        options.workspaceId,
        options.runId,
        logCursor,
      );
      aggregatedLines = mergeCappedLines(aggregatedLines, lines);
      return {
        status: latestRun.status,
        lines: aggregatedLines,
        ts: resolveRunTimestamp(latestRun, options.clock),
      };
    }

    await options.sleep(resolvePollDelay(iteration));
    latestRun = await workspaceService.getWorkflowRun(options.workspaceId, options.runId);
  }

  const lines = await readAvailableLogs(
    workspaceService,
    options.workspaceId,
    options.runId,
    logCursor,
  );
  aggregatedLines = mergeCappedLines(aggregatedLines, lines);
  return {
    status: latestRun.status,
    lines: mergeCappedLines(aggregatedLines, [
      { type: "warn", msg: "Run still active after polling window ended" },
    ]),
    ts: resolveRunTimestamp(latestRun, options.clock),
  };
}
