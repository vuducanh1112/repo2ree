import type { AppShellClock } from "@shell/app/bootstrap/ports";
import type { ExecutionRunsClient } from "@shell/data/execution-runs/client";
import { observeExecutionRun } from "@shell/data/execution-runs/queries";
import type { QueryClient } from "@tanstack/react-query";

interface PollExecutionRunOptions {
  reeId: string;
  runId: string;
  maxIterations?: number;
  onUpdate?: (update: PollExecutionRunResult) => void;
  clock: AppShellClock;
  sleep: (ms: number) => Promise<void>;
}

interface PollExecutionRunResult {
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

export async function pollExecutionRun(
  queryClient: QueryClient,
  executionRunsClient: ExecutionRunsClient,
  options: PollExecutionRunOptions,
): Promise<PollExecutionRunResult> {
  void options.clock;
  void options.sleep;
  return observeExecutionRun(queryClient, executionRunsClient, {
    reeId: options.reeId,
    runId: options.runId,
    onUpdate: options.onUpdate,
    timeoutMs: (options.maxIterations || 90) * 1500,
    sleep: options.sleep,
  });
}
