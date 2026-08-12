import type { LogEntry } from "@core/ree/ReeTypes";
import type { ReeRun } from "@core/runs/ReeRun";
import { useReeRunLogsQuery, useReeRunQuery } from "@shell/data/runs/queries";
import { type ReactNode, useMemo } from "react";
import type { useAppShell } from "../../hooks/useAppShell";
import styles from "./pageContainers.module.css";

export type AppShellController = ReturnType<typeof useAppShell>;

export interface AppShellPageContainerProps {
  ree: AppShellController["ree"];
  reeIntent: AppShellController["reeIntent"];
  workspaceRemote: AppShellController["workspaceRemote"];
  stepRuns: AppShellController["stepRuns"];
  uiChrome: AppShellController["uiChrome"];
  evaluation: AppShellController["evaluation"];
  currentReeFiles: AppShellController["currentReeFiles"];
  commands: AppShellController["commands"];
  sealRunning: AppShellController["sealRunning"];
  sealLog: AppShellController["sealLog"];
}

export function ContentSection({ children }: { children: ReactNode }) {
  return <div className={styles.contentSection}>{children}</div>;
}

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
    const runTimestamp = resolveStepRunTimestamp(runQuery.data, args.fallbackTimestamp);
    return {
      lines: logsQuery.data?.lines ?? [],
      ts: runTimestamp,
    };
  }, [args.fallbackTimestamp, args.runId, logsQuery.data?.lines, runQuery.data]);
}

function resolveStepRunTimestamp(run: ReeRun | undefined, fallback?: string): string {
  return (
    run?.finishedAt || run?.startedAt || run?.createdAt || fallback || new Date().toISOString()
  );
}
