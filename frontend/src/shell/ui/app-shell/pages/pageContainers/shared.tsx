import { type CSSProperties, type ReactNode, useMemo } from "react";
import type { ExecutionRun } from "../../../../../core/execution/ExecutionRun";
import type { LogEntry } from "../../../../../core/ree/ReeTypes";
import {
  useExecutionRunLogsQuery,
  useExecutionRunQuery,
} from "../../../../data/execution-runs/queries";
import type { useAppShell } from "../../hooks/useAppShell";

export type AppShellController = ReturnType<typeof useAppShell>;

export interface AppShellPageContainerProps {
  ree: AppShellController["ree"];
  inclusionState: AppShellController["inclusionState"];
  reeDraft: AppShellController["reeDraft"];
  workspaceRemote: AppShellController["workspaceRemote"];
  assemblyRun: AppShellController["assemblyRun"];
  uiChrome: AppShellController["uiChrome"];
  level: AppShellController["level"];
  currentReeFiles: AppShellController["currentReeFiles"];
  commands: AppShellController["commands"];
}

const CONTENT_SECTION_STYLE: CSSProperties = {
  flex: 1,
  overflow: "hidden",
  display: "flex",
  flexDirection: "column",
};

export function ContentSection({ children }: { children: ReactNode }) {
  return <div style={CONTENT_SECTION_STYLE}>{children}</div>;
}

export function useAssemblyRunLogEntry(args: {
  reeId: string;
  runId: string | undefined;
  fallbackTimestamp?: string;
}): LogEntry | null {
  const runQuery = useExecutionRunQuery(args.reeId, args.runId);
  const logsQuery = useExecutionRunLogsQuery(args.reeId, args.runId);

  return useMemo(() => {
    if (!args.runId) {
      return null;
    }
    const runTimestamp = resolveAssemblyRunTimestamp(runQuery.data, args.fallbackTimestamp);
    return {
      lines: logsQuery.data?.lines ?? [],
      ts: runTimestamp,
    };
  }, [args.fallbackTimestamp, args.runId, logsQuery.data?.lines, runQuery.data]);
}

function resolveAssemblyRunTimestamp(run: ExecutionRun | undefined, fallback?: string): string {
  return (
    run?.finishedAt || run?.startedAt || run?.createdAt || fallback || new Date().toISOString()
  );
}
