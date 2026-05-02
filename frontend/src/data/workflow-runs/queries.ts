import { type QueryClient, queryOptions } from "@tanstack/react-query";
import type { WorkspaceRuntimeValue } from "../../app/browser/BrowserRuntime";
import type {
  LogLine,
  WorkflowRunLogChunk,
  WorkflowRunRecord,
  WorkflowRunStatus,
} from "../../application/ports/repositoryTypes";
import { resolveWorkspaceId } from "../client";
import { queryKeys } from "../queryKeys";

const TERMINAL_STATUSES = new Set<WorkflowRunStatus>(["succeeded", "failed", "canceled"]);
const MAX_LOG_LINES = 2000;
const MAX_LOG_MESSAGE_CHARS = 4000;
const MAX_LOG_PAGES = 20;

function sanitizeLine(line: LogLine): LogLine {
  if (line.msg.length <= MAX_LOG_MESSAGE_CHARS) {
    return line;
  }
  return {
    ...line,
    msg: `${line.msg.slice(0, MAX_LOG_MESSAGE_CHARS)}... [truncated]`,
  };
}

function mergeCappedLines(existing: LogLine[], incoming: LogLine[]): LogLine[] {
  if (incoming.length === 0) {
    return existing;
  }
  const merged = [...existing, ...incoming.map(sanitizeLine)];
  if (merged.length <= MAX_LOG_LINES) {
    return merged;
  }
  return merged.slice(merged.length - MAX_LOG_LINES);
}

function isTerminalWorkflowRunStatus(status?: WorkflowRunStatus): boolean {
  return status ? TERMINAL_STATUSES.has(status) : false;
}

function resolveRunTimestamp(run: WorkflowRunRecord | undefined, fallback: string): string {
  return run?.finishedAt || run?.startedAt || run?.createdAt || fallback;
}

function createWorkflowRunQueryOptions(
  runtime: WorkspaceRuntimeValue,
  workspaceId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: queryKeys.workflowRun(workspaceId, runId),
    queryFn: () => runtime.workflowRunRepository.getWorkflowRun(workspaceId, runId),
  });
}

function createWorkflowRunLogsQueryOptions(
  runtime: WorkspaceRuntimeValue,
  workspaceId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: queryKeys.workflowRunLogs(workspaceId, runId),
    queryFn: async (): Promise<WorkflowRunLogChunk> => {
      let cursor: string | undefined;
      let chunk: WorkflowRunLogChunk | undefined;
      let lines: LogLine[] = [];

      for (let page = 0; page < MAX_LOG_PAGES; page += 1) {
        chunk = await runtime.workflowRunRepository.getWorkflowRunLogs(workspaceId, runId, cursor);
        lines = mergeCappedLines(lines, chunk.lines);
        if (!chunk.hasMore) {
          break;
        }
        cursor = chunk.nextCursor || cursor;
        if (!cursor) {
          break;
        }
      }

      return {
        lines,
        hasMore: false,
      };
    },
  });
}

async function fetchWorkflowRun(
  queryClient: QueryClient,
  runtime: WorkspaceRuntimeValue,
  workspaceId: string,
  runId: string,
) {
  return queryClient.fetchQuery(createWorkflowRunQueryOptions(runtime, workspaceId, runId));
}

async function fetchWorkflowRunLogs(
  queryClient: QueryClient,
  runtime: WorkspaceRuntimeValue,
  workspaceId: string,
  runId: string,
) {
  return queryClient.fetchQuery(createWorkflowRunLogsQueryOptions(runtime, workspaceId, runId));
}

export async function observeWorkflowRun(
  queryClient: QueryClient,
  runtime: WorkspaceRuntimeValue,
  args: {
    workspaceId?: string;
    runId: string;
    onUpdate?: (update: { status: WorkflowRunStatus; lines: LogLine[]; ts: string }) => void;
    timeoutMs?: number;
    sleep?: (ms: number) => Promise<void>;
  },
) {
  const workspaceId = resolveWorkspaceId(runtime, args.workspaceId);
  const startedAt = Date.now();
  const sleep =
    args.sleep ??
    ((ms: number) => new Promise<void>((resolve) => globalThis.setTimeout(resolve, ms)));

  while (true) {
    const run = await fetchWorkflowRun(queryClient, runtime, workspaceId, args.runId);
    const logs = await fetchWorkflowRunLogs(queryClient, runtime, workspaceId, args.runId);
    const snapshot = {
      status: run.status,
      lines: logs.lines,
      ts: resolveRunTimestamp(run, new Date().toISOString()),
    };

    args.onUpdate?.(snapshot);

    if (isTerminalWorkflowRunStatus(run.status)) {
      return snapshot;
    }

    if (args.timeoutMs && Date.now() - startedAt > args.timeoutMs) {
      return {
        ...snapshot,
        lines: mergeCappedLines(snapshot.lines, [
          { type: "warn", msg: "Run still active after polling window ended" },
        ]),
      };
    }

    await sleep(1500);
  }
}
