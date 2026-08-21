import type { LogEntry } from "@core/ree/ReeTypes";
import { resolveReeRunTimestamp } from "@core/runs/runTimestamp";
import { useReeRunLogsQuery, useReeRunQuery } from "@shell/data/runs/queries";
import { useMemo } from "react";

export function useStepRunLogEntry(args: {
  reeId: string;
  runId: string | undefined;
  fallbackTimestamp?: string;
}): LogEntry | null {
  const runQuery = useReeRunQuery(args.reeId, args.runId);
  const logsQuery = useReeRunLogsQuery(args.reeId, args.runId);

  return useMemo(() => {
    if (!args.runId) {
      return null;
    }
    return {
      lines: logsQuery.data?.lines ?? [],
      ts: resolveReeRunTimestamp(runQuery.data, args.fallbackTimestamp ?? new Date().toISOString()),
    };
  }, [args.fallbackTimestamp, args.runId, logsQuery.data?.lines, runQuery.data]);
}
