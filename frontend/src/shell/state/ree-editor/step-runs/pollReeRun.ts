import type { AppShellClock } from "@shell/app/bootstrap/ports";
import type { ReeRunsClient } from "@shell/data/runs/client";
import { observeReeRun } from "@shell/data/runs/queries";
import type { QueryClient } from "@tanstack/react-query";

interface PollReeRunOptions {
  reeId: string;
  runId: string;
  maxIterations?: number;
  onUpdate?: (update: PollReeRunResult) => void;
  clock: AppShellClock;
  sleep: (ms: number) => Promise<void>;
}

interface PollReeRunResult {
  status:
    | "created"
    | "queued"
    | "provisioning"
    | "running"
    | "succeeded"
    | "failed"
    | "canceling"
    | "canceled";
  lines: Array<{ type: "info" | "ok" | "warn" | "err" | "out"; msg: string; ts?: string }>;
  ts: string;
}

export async function pollReeRun(
  queryClient: QueryClient,
  executionRunsClient: ReeRunsClient,
  options: PollReeRunOptions,
): Promise<PollReeRunResult> {
  void options.clock;
  return observeReeRun(queryClient, executionRunsClient, {
    reeId: options.reeId,
    runId: options.runId,
    onUpdate: options.onUpdate,
    timeoutMs: options.maxIterations ? options.maxIterations * 1500 : undefined,
    sleep: options.sleep,
  });
}
