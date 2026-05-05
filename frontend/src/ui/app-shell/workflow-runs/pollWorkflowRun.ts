import type { QueryClient } from "@tanstack/react-query";
import type { AppShellClock } from "../../../app/bootstrap/ports";
import type { ExecutionRunsClient } from "../../../data/execution-runs/client";
import { observeExecutionRun } from "../../../data/execution-runs/queries";

interface PollWorkflowRunOptions {
  reeId: string;
  runId: string;
  maxIterations?: number;
  onUpdate?: (update: PollWorkflowRunResult) => void;
  clock: AppShellClock;
  sleep: (ms: number) => Promise<void>;
}

interface PollWorkflowRunResult {
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

export async function pollWorkflowRun(
  queryClient: QueryClient,
  workflowRunsClient: ExecutionRunsClient,
  options: PollWorkflowRunOptions,
): Promise<PollWorkflowRunResult> {
  void options.clock;
  void options.sleep;
  return observeExecutionRun(queryClient, workflowRunsClient, {
    reeId: options.reeId,
    runId: options.runId,
    onUpdate: options.onUpdate,
    timeoutMs: (options.maxIterations || 90) * 1500,
    sleep: options.sleep,
  });
}
