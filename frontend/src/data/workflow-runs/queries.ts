import { type QueryClient, queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";
import type { LogLine } from "../../domain/ree/ReeTypes";
import type {
  WorkflowRunLogChunk,
  WorkflowRunRecord,
  WorkflowRunStatus,
} from "../../domain/workflow/WorkflowRun";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
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
  reeId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: queryKeys.workflowRun(reeId, runId),
    queryFn: () => workflowRunsClient.getWorkflowRun(reeId, runId),
  });
}

function createWorkflowRunLogsQueryOptions(
  workflowRunsClient: WorkflowRunsClient,
  reeId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: queryKeys.workflowRunLogs(reeId, runId),
    queryFn: async (): Promise<WorkflowRunLogChunk> => {
      let cursor: string | undefined;
      let chunk: WorkflowRunLogChunk | undefined;
      let lines: LogLine[] = [];

      for (let page = 0; page < MAX_LOG_PAGES; page += 1) {
        chunk = await workflowRunsClient.getWorkflowRunLogs(reeId, runId, cursor);
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
  reeId: string,
  runId: string,
) {
  return queryClient.fetchQuery(createWorkflowRunQueryOptions(workflowRunsClient, reeId, runId));
}

async function fetchWorkflowRunLogs(
  queryClient: QueryClient,
  workflowRunsClient: WorkflowRunsClient,
  reeId: string,
  runId: string,
) {
  return queryClient.fetchQuery(
    createWorkflowRunLogsQueryOptions(workflowRunsClient, reeId, runId),
  );
}

export function useWorkflowRunQuery(reeId: string | undefined, runId: string | undefined) {
  const runtime = useApiRuntime();
  const workflowRunsClient = useWorkflowRunsClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useQuery({
    ...(runId
      ? createWorkflowRunQueryOptions(workflowRunsClient, resolvedReeId, runId)
      : {
          queryKey: queryKeys.workflowRun(resolvedReeId, "idle"),
          queryFn: async () => {
            throw new Error("Workflow run query is disabled");
          },
        }),
    enabled: !!runId,
    refetchInterval: (query) =>
      isTerminalWorkflowRunStatus(query.state.data?.status) ? false : 1500,
  });
}

export function useWorkflowRunLogsQuery(reeId: string | undefined, runId: string | undefined) {
  const runtime = useApiRuntime();
  const workflowRunsClient = useWorkflowRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);
  const baseOptions = runId
    ? createWorkflowRunLogsQueryOptions(workflowRunsClient, resolvedReeId, runId)
    : {
        queryKey: queryKeys.workflowRunLogs(resolvedReeId, "idle"),
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
        queryKeys.workflowRun(resolvedReeId, runId),
      );
      return isTerminalWorkflowRunStatus(run?.status) ? false : 1500;
    },
  });
}

export async function observeWorkflowRun(
  queryClient: QueryClient,
  workflowRunsClient: WorkflowRunsClient,
  args: {
    reeId: string;
    runId: string;
    onUpdate?: (update: { status: WorkflowRunStatus; lines: LogLine[]; ts: string }) => void;
    timeoutMs?: number;
    sleep?: (ms: number) => Promise<void>;
  },
) {
  const reeId = args.reeId;
  const startedAt = Date.now();
  const sleep =
    args.sleep ??
    ((ms: number) => new Promise<void>((resolve) => globalThis.setTimeout(resolve, ms)));

  while (true) {
    const run = await fetchWorkflowRun(queryClient, workflowRunsClient, reeId, args.runId);
    const logs = await fetchWorkflowRunLogs(queryClient, workflowRunsClient, reeId, args.runId);
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
