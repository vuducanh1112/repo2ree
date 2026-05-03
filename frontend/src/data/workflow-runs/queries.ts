import { type QueryClient, queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";
import type { LogLine } from "../../domain/ree/ReeTypes";
import type {
  WorkflowRunLogChunk,
  WorkflowRunRecord,
  WorkflowRunStatus,
} from "../../domain/workflow/WorkflowRun";
import { useApiRuntime } from "../apiRuntime";
import { resolveWorkspaceId } from "../client";
import { queryKeys } from "../queryKeys";
import type { WorkflowRunsClient } from "./client";
import { useWorkflowRunsClient } from "./client";

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
  workflowRunsClient: WorkflowRunsClient,
  workspaceId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: queryKeys.workflowRun(workspaceId, runId),
    queryFn: () => workflowRunsClient.getWorkflowRun(workspaceId, runId),
  });
}

function createWorkflowRunLogsQueryOptions(
  workflowRunsClient: WorkflowRunsClient,
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
        chunk = await workflowRunsClient.getWorkflowRunLogs(workspaceId, runId, cursor);
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
  workflowRunsClient: WorkflowRunsClient,
  workspaceId: string,
  runId: string,
) {
  return queryClient.fetchQuery(
    createWorkflowRunQueryOptions(workflowRunsClient, workspaceId, runId),
  );
}

async function fetchWorkflowRunLogs(
  queryClient: QueryClient,
  workflowRunsClient: WorkflowRunsClient,
  workspaceId: string,
  runId: string,
) {
  return queryClient.fetchQuery(
    createWorkflowRunLogsQueryOptions(workflowRunsClient, workspaceId, runId),
  );
}

export function useWorkflowRunQuery(workspaceId: string | undefined, runId: string | undefined) {
  const runtime = useApiRuntime();
  const workflowRunsClient = useWorkflowRunsClient();
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);

  return useQuery({
    ...(runId
      ? createWorkflowRunQueryOptions(workflowRunsClient, resolvedWorkspaceId, runId)
      : {
          queryKey: queryKeys.workflowRun(resolvedWorkspaceId, "idle"),
          queryFn: async () => {
            throw new Error("Workflow run query is disabled");
          },
        }),
    enabled: !!runId,
    refetchInterval: (query) =>
      isTerminalWorkflowRunStatus(query.state.data?.status) ? false : 1500,
  });
}

export function useWorkflowRunLogsQuery(
  workspaceId: string | undefined,
  runId: string | undefined,
) {
  const runtime = useApiRuntime();
  const workflowRunsClient = useWorkflowRunsClient();
  const queryClient = useQueryClient();
  const resolvedWorkspaceId = resolveWorkspaceId(runtime, workspaceId);
  const baseOptions = runId
    ? createWorkflowRunLogsQueryOptions(workflowRunsClient, resolvedWorkspaceId, runId)
    : {
        queryKey: queryKeys.workflowRunLogs(resolvedWorkspaceId, "idle"),
        queryFn: async () => {
          throw new Error("Workflow run logs query is disabled");
        },
      };

  return useQuery({
    ...baseOptions,
    enabled: !!runId,
    refetchInterval: () => {
      if (!runId) {
        return false;
      }
      const run = queryClient.getQueryData<WorkflowRunRecord>(
        queryKeys.workflowRun(resolvedWorkspaceId, runId),
      );
      return isTerminalWorkflowRunStatus(run?.status) ? false : 1500;
    },
  });
}

export async function observeWorkflowRun(
  queryClient: QueryClient,
  workflowRunsClient: WorkflowRunsClient,
  args: {
    workspaceId: string;
    runId: string;
    onUpdate?: (update: { status: WorkflowRunStatus; lines: LogLine[]; ts: string }) => void;
    timeoutMs?: number;
    sleep?: (ms: number) => Promise<void>;
  },
) {
  const workspaceId = args.workspaceId;
  const startedAt = Date.now();
  const sleep =
    args.sleep ??
    ((ms: number) => new Promise<void>((resolve) => globalThis.setTimeout(resolve, ms)));

  while (true) {
    const run = await fetchWorkflowRun(queryClient, workflowRunsClient, workspaceId, args.runId);
    const logs = await fetchWorkflowRunLogs(
      queryClient,
      workflowRunsClient,
      workspaceId,
      args.runId,
    );
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
