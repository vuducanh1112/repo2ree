import { DEFAULT_REE_ID } from "@core/ree/ReeId";
import type { LogLine } from "@core/ree/ReeTypes";
import type { ReeRun, ReeRunLogChunk, ReeRunSummary } from "@core/runs/ReeRun";
import type { ReeRunStatus } from "@core/runs/ReeRunStatus";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { type QueryClient, queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import type { ReeRunsClient } from "./client";
import { useReeRunsClient } from "./client";

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

function resolveRunTimestamp(run: ReeRun | undefined, fallback: string): string {
  return run?.finishedAt || run?.startedAt || run?.createdAt || fallback;
}

function createReeRunQueryOptions(
  executionRunsClient: ReeRunsClient,
  reeId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: queryKeys.stepRuns(reeId, runId),
    queryFn: () => executionRunsClient.getReeRun(reeId, runId),
  });
}

function createReeRunLogsQueryOptions(
  executionRunsClient: ReeRunsClient,
  reeId: string,
  runId: string,
) {
  return queryOptions({
    queryKey: queryKeys.stepRunLogs(reeId, runId),
    queryFn: async (): Promise<ReeRunLogChunk> => {
      let cursor: string | undefined;
      let chunk: ReeRunLogChunk | undefined;
      let lines: LogLine[] = [];

      for (let page = 0; page < MAX_LOG_PAGES; page += 1) {
        chunk = await executionRunsClient.getReeRunLogs(reeId, runId, cursor);
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

async function fetchReeRun(
  queryClient: QueryClient,
  executionRunsClient: ReeRunsClient,
  reeId: string,
  runId: string,
) {
  return queryClient.fetchQuery(createReeRunQueryOptions(executionRunsClient, reeId, runId));
}

async function fetchReeRunLogs(
  queryClient: QueryClient,
  executionRunsClient: ReeRunsClient,
  reeId: string,
  runId: string,
) {
  return queryClient.fetchQuery(createReeRunLogsQueryOptions(executionRunsClient, reeId, runId));
}

// How briskly anything in flight is polled — the run listing that drives the
// always-mounted logs HUD, a single run and its logs, and the imperative
// observer below. One constant so the app's responsiveness is retuned in one
// place instead of five.
const RUNS_ACTIVE_POLL_MS = 1500;
// Nothing in flight: still often enough to notice runs started outside this tab,
// e.g. by an agent.
const RUNS_IDLE_POLL_MS = 5000;

export function useReeRunsQuery(reeId?: string) {
  const runtime = useApiRuntime();
  const executionRunsClient = useReeRunsClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useQuery({
    queryKey: queryKeys.reeRuns(resolvedReeId),
    queryFn: (): Promise<ReeRunSummary[]> => executionRunsClient.listReeRuns(resolvedReeId),
    // The sentinel id means "no REE yet" — polling through ensureReeId with it
    // would lazily *create* one, which a passive listing must never do.
    enabled: !!resolvedReeId && resolvedReeId !== DEFAULT_REE_ID,
    refetchInterval: (query) => {
      const anyActive = query.state.data?.some((run) => !isTerminalReeRunStatus(run.status));
      return anyActive ? RUNS_ACTIVE_POLL_MS : RUNS_IDLE_POLL_MS;
    },
  });
}

export function useReeRunQuery(reeId: string | undefined, runId: string | undefined) {
  const runtime = useApiRuntime();
  const executionRunsClient = useReeRunsClient();
  const resolvedReeId = resolveReeId(runtime, reeId);

  return useQuery({
    ...(runId
      ? createReeRunQueryOptions(executionRunsClient, resolvedReeId, runId)
      : {
          queryKey: queryKeys.stepRuns(resolvedReeId, "idle"),
          queryFn: async () => {
            throw new Error("Execution run query is disabled");
          },
        }),
    enabled: !!runId,
    refetchInterval: (query) =>
      isTerminalReeRunStatus(query.state.data?.status) ? false : RUNS_ACTIVE_POLL_MS,
  });
}

export function useReeRunLogsQuery(reeId: string | undefined, runId: string | undefined) {
  const runtime = useApiRuntime();
  const executionRunsClient = useReeRunsClient();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, reeId);
  const baseOptions = runId
    ? createReeRunLogsQueryOptions(executionRunsClient, resolvedReeId, runId)
    : {
        queryKey: queryKeys.stepRunLogs(resolvedReeId, "idle"),
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
      const run = queryClient.getQueryData<ReeRun>(queryKeys.stepRuns(resolvedReeId, runId));
      return isTerminalReeRunStatus(run?.status) ? false : RUNS_ACTIVE_POLL_MS;
    },
  });
}

export async function observeReeRun(
  queryClient: QueryClient,
  executionRunsClient: ReeRunsClient,
  args: {
    reeId: string;
    runId: string;
    onUpdate?: (update: { status: ReeRunStatus; lines: LogLine[]; ts: string }) => void;
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
    const run = await fetchReeRun(queryClient, executionRunsClient, reeId, args.runId);
    const logs = await fetchReeRunLogs(queryClient, executionRunsClient, reeId, args.runId);
    const snapshot = {
      status: run.status,
      failure: run.failure,
      lines: logs.lines,
      ts: resolveRunTimestamp(run, new Date().toISOString()),
    };

    args.onUpdate?.(snapshot);

    if (isTerminalReeRunStatus(run.status)) {
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

    await sleep(RUNS_ACTIVE_POLL_MS);
  }
}
