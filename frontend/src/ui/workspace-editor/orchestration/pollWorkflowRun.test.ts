import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { WorkflowRunRepository } from "../../../application/ports/WorkflowRunRepository";
import type { WorkspaceEditorClock } from "../../../application/workspace-editor/WorkspaceEditorPorts";
import { pollWorkflowRun } from "./pollWorkflowRun";

const clock: WorkspaceEditorClock = {
  nowIso: () => "2026-04-29T00:00:00.000Z",
  nowMillis: () => 1777420800000,
};

describe("pollWorkflowRun", () => {
  it("uses injected sleep between non-terminal polls", async () => {
    const queryClient = new QueryClient();
    const sleep = vi.fn(async () => {});
    const getWorkflowRun = vi
      .fn<WorkflowRunRepository["getWorkflowRun"]>()
      .mockResolvedValueOnce({
        runId: "run-1",
        status: "running",
        createdAt: "2026-04-29T00:00:00.000Z",
      })
      .mockResolvedValueOnce({
        runId: "run-1",
        status: "succeeded",
        createdAt: "2026-04-29T00:00:00.000Z",
        finishedAt: "2026-04-29T00:00:01.000Z",
      });
    const workflowRunRepository = {
      getWorkflowRun,
      getWorkflowRunLogs: vi.fn(async () => ({ lines: [], hasMore: false })),
      startWorkflowRun: vi.fn(),
      cancelWorkflowRun: vi.fn(),
    } as unknown as WorkflowRunRepository;

    const result = await pollWorkflowRun(queryClient, workflowRunRepository, {
      workspaceId: "active",
      runId: "run-1",
      maxIterations: 3,
      clock,
      sleep,
    });

    expect(sleep).toHaveBeenCalledWith(1000);
    expect(result.status).toBe("succeeded");
    expect(result.ts).toBe("2026-04-29T00:00:01.000Z");
  });
});
