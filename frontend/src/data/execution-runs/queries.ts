import { type QueryClient, queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ExecutionRun, ExecutionRunLogChunk } from "../../domain/execution/ExecutionRun";
import type { ExecutionRunStatus } from "../../domain/execution/ExecutionRunStatus";
import type { LogLine } from "../../domain/ree/ReeTypes";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import type { ExecutionRunsClient } from "./client";
import { useExecutionRunsClient } from "./client";

const TERMINAL_STATUSES = new Set<ExecutionRunStatus>(["succeeded", "failed", "canceled"]);
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

function isTerminalExecutionRunStatus(status?: ExecutionRunStatus): boolean {
  return status ? TERMINAL_STATUSES.has(status) : false;
}

function resolveRunTimestamp(run: ExecutionRun | undefined, fallback: string): string {
  return run?.finishedAt || run?.startedAt || run?.createdAt || fallback;
}

function createExecutionRunQueryOptions(
  executionRunsClient: ExecutionRunsClient,
  reeId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: queryKeys.workflowRun(reeId, runId),
    queryFn: () => executionRunsClient.getExecutionRun(reeId, runId),
  });
}

function createExecutionRunLogsQueryOptions(
  executionRunsClient: ExecutionRunsClient,
  reeId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: queryKeys.workflowRunLogs(reeId, runId),
    queryFn: async (): Promise<ExecutionRunLogChunk> => {
      let cursor: string | undefined;
      let chunk: ExecutionRunLogChunk | undefined;
      let lines: LogLine[] = [];

      for (let page = 0; page < MAX_LOG_PAGES; page += 1) {
        chunk = await executionRunsClient.getExecutionRunLogs(reeId, runId, cursor);
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

async function fetchExecutionRun(
  queryClient: QueryClient,
  executionRunsClient: ExecutionRunsClient,
  reeId: string,
  runId: string,
) {
  return queryClient.fetchQuery(createExecutionRunQueryOptions(executionRunsClient, reeId, runId));
}

async function fetchExecutionRunLogs(
  queryClient: QueryClient,
  executionRunsClient: ExecutionRunsClient,
  reeId: string,
  runId: string,
) {
  return queryClient.fetchQuery(
    createExecutionRunLogsQueryOptions(executionRunsClient, reeId, runId),
  );
}

export function useExecutionRunQuery(reeId: string | undefined, runId: string | undefined) {
  const runtime = useApiRuntime();
  const executionRunsClient = useExecutionRunsClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useQuery({
    ...(runId
      ? createExecutionRunQueryOptions(executionRunsClient, resolvedReeId, runId)
      : {
          queryKey: queryKeys.workflowRun(resolvedReeId, "idle"),
          queryFn: async () => {
            throw new Error("Execution run query is disabled");
          },
        }),
    enabled: !!runId,
    refetchInterval: (query) =>
      isTerminalExecutionRunStatus(query.state.data?.status) ? false : 1500,
  });
}

export function useExecutionRunLogsQuery(reeId: string | undefined, runId: string | undefined) {
  const runtime = useApiRuntime();
  const executionRunsClient = useExecutionRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);
  const baseOptions = runId
    ? createExecutionRunLogsQueryOptions(executionRunsClient, resolvedReeId, runId)
    : {
        queryKey: queryKeys.workflowRunLogs(resolvedReeId, "idle"),
        queryFn: async () => {
          throw new Error("Execution run logs query is disabled");
        },
      };

  return useQuery({
    ...baseOptions,
    enabled: !!runId,
    refetchInterval: () => {
      if (!runId) {
        return false;
      }
      const run = queryClient.getQueryData<ExecutionRun>(
        queryKeys.workflowRun(resolvedReeId, runId),
      );
      return isTerminalExecutionRunStatus(run?.status) ? false : 1500;
    },
  });
}

export async function observeExecutionRun(
  queryClient: QueryClient,
  executionRunsClient: ExecutionRunsClient,
  args: {
    reeId: string;
    runId: string;
    onUpdate?: (update: { status: ExecutionRunStatus; lines: LogLine[]; ts: string }) => void;
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
    const run = await fetchExecutionRun(queryClient, executionRunsClient, reeId, args.runId);
    const logs = await fetchExecutionRunLogs(queryClient, executionRunsClient, reeId, args.runId);
    const snapshot = {
      status: run.status,
      lines: logs.lines,
      ts: resolveRunTimestamp(run, new Date().toISOString()),
    };

    args.onUpdate?.(snapshot);

    if (isTerminalExecutionRunStatus(run.status)) {
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
