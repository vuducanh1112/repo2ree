import type { QueryClient } from "@tanstack/react-query";
import type { WorkspaceRuntimeValue } from "../../../app/browser/BrowserRuntime";
import type { AppShellClock } from "../../../application/app-shell/AppShellPorts";
import type { WorkflowRunRepository } from "../../../application/ports/WorkflowRunRepository";
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
  workflowRunRepository: WorkflowRunRepository,
  options: PollWorkflowRunOptions,
): Promise<PollWorkflowRunResult> {
  void options.clock;
  void options.sleep;
  const runtime = {
    workspaceId: options.workspaceId,
    workflowRunRepository,
  } as WorkspaceRuntimeValue;
  return observeWorkflowRun(queryClient, runtime, {
    workspaceId: options.workspaceId,
    runId: options.runId,
    onUpdate: options.onUpdate,
    timeoutMs: (options.maxIterations || 90) * 1500,
    sleep: options.sleep,
  });
}
