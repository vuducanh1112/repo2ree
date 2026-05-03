import type { QueryClient } from "@tanstack/react-query";
import type { AppShellClock } from "../../../application/app-shell/AppShellPorts";
import type { WorkflowRunsClient } from "../../../data/workflow-runs/client";
import { observeWorkflowRun } from "../../../data/workflow-runs/queries";

interface PollWorkflowRunOptions {
  workspaceId: string;
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
  workflowRunsClient: WorkflowRunsClient,
  options: PollWorkflowRunOptions,
): Promise<PollWorkflowRunResult> {
  void options.clock;
  void options.sleep;
  return observeWorkflowRun(queryClient, workflowRunsClient, {
    workspaceId: options.workspaceId,
    runId: options.runId,
    onUpdate: options.onUpdate,
    timeoutMs: (options.maxIterations || 90) * 1500,
    sleep: options.sleep,
  });
}
