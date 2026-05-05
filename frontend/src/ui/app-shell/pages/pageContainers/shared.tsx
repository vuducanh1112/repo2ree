import { type CSSProperties, type ReactNode, useMemo } from "react";
import {
  useWorkflowRunLogsQuery,
  useWorkflowRunQuery,
} from "../../../../data/workflow-runs/queries";
import type { LogEntry } from "../../../../domain/ree/ReeTypes";
import type { WorkflowRunRecord } from "../../../../domain/workflow/WorkflowRun";
import type { useAppShell } from "../../hooks/useAppShell";

export type AppShellController = ReturnType<typeof useAppShell>;

export interface AppShellPageContainerProps {
  ree: AppShellController["ree"];
  reeDraft: AppShellController["reeDraft"];
  workspaceRemote: AppShellController["workspaceRemote"];
  workflowRun: AppShellController["workflowRun"];
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

export function useWorkflowLogEntry(args: {
  reeId: string;
  runId: string | undefined;
  fallbackTimestamp?: string;
}): LogEntry | null {
  const runQuery = useWorkflowRunQuery(args.reeId, args.runId);
  const logsQuery = useWorkflowRunLogsQuery(args.reeId, args.runId);

  return useMemo(() => {
    if (!args.runId) {
      return null;
    }
    const runTimestamp = resolveWorkflowRunTimestamp(runQuery.data, args.fallbackTimestamp);
    return {
      lines: logsQuery.data?.lines ?? [],
      ts: runTimestamp,
    };
  }, [args.fallbackTimestamp, args.runId, logsQuery.data?.lines, runQuery.data]);
}

function resolveWorkflowRunTimestamp(
  run: WorkflowRunRecord | undefined,
  fallback?: string,
): string {
  return (
    run?.finishedAt || run?.startedAt || run?.createdAt || fallback || new Date().toISOString()
  );
}
