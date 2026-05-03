import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { AppShellClock } from "../../../application/app-shell/AppShellPorts";
import type { WorkflowRunsClient } from "../../../data/workflow-runs/client";
import { pollWorkflowRun } from "./pollWorkflowRun";

const clock: AppShellClock = {
  nowIso: () => "2026-04-29T00:00:00.000Z",
  nowMillis: () => 1777420800000,
};

function createWorkflowRunsClient(overrides: Partial<WorkflowRunsClient>): WorkflowRunsClient {
  return {
    getWorkflowRun: vi.fn(),
    getWorkflowRunLogs: vi.fn(async () => ({ lines: [], hasMore: false })),
    startWorkflowRun: vi.fn(),
    cancelWorkflowRun: vi.fn(),
    ...overrides,
  } as WorkflowRunsClient;
}

describe("pollWorkflowRun", () => {
  it("stops polling after a run succeeds", async () => {
    const queryClient = new QueryClient();
    const sleep = vi.fn(async () => {});
    const getWorkflowRun = vi
      .fn<WorkflowRunsClient["getWorkflowRun"]>()
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
    const workflowRunsClient = createWorkflowRunsClient({
      getWorkflowRun,
      getWorkflowRunLogs: vi
        .fn<WorkflowRunsClient["getWorkflowRunLogs"]>()
        .mockResolvedValue({ lines: [{ type: "ok", msg: "done" }], hasMore: false }),
    });

    const result = await pollWorkflowRun(queryClient, workflowRunsClient, {
      workspaceId: "active",
      runId: "run-1",
      maxIterations: 3,
      clock,
      sleep,
    });

    expect(sleep).toHaveBeenCalledTimes(1);
    expect(result.status).toBe("succeeded");
    expect(result.lines.at(-1)?.msg).toBe("done");
    expect(result.ts).toBe("2026-04-29T00:00:01.000Z");
  });

  it("stops polling after a run is canceled", async () => {
    const queryClient = new QueryClient();
    const sleep = vi.fn(async () => {});
    const workflowRunsClient = createWorkflowRunsClient({
      getWorkflowRun: vi
        .fn<WorkflowRunsClient["getWorkflowRun"]>()
        .mockResolvedValueOnce({
          runId: "run-2",
          status: "running",
          createdAt: "2026-04-29T00:00:00.000Z",
        })
        .mockResolvedValueOnce({
          runId: "run-2",
          status: "canceled",
          createdAt: "2026-04-29T00:00:00.000Z",
          finishedAt: "2026-04-29T00:00:01.000Z",
        }),
    });

    const result = await pollWorkflowRun(queryClient, workflowRunsClient, {
      workspaceId: "active",
      runId: "run-2",
      maxIterations: 3,
      clock,
      sleep,
    });

    expect(sleep).toHaveBeenCalledTimes(1);
    expect(result.status).toBe("canceled");
  });

  it("surfaces workflow run fetch errors", async () => {
    const queryClient = new QueryClient();
    const workflowRunsClient = createWorkflowRunsClient({
      getWorkflowRun: vi.fn(async () => {
        throw new Error("backend unavailable");
      }),
    });

    await expect(
      pollWorkflowRun(queryClient, workflowRunsClient, {
        workspaceId: "active",
        runId: "run-3",
        maxIterations: 1,
        clock,
        sleep: vi.fn(async () => {}),
      }),
    ).rejects.toThrow("backend unavailable");
  });

  it("keeps workspace-specific run snapshots isolated by query key", async () => {
    const queryClient = new QueryClient();
    const sleep = vi.fn(async () => {});
    const getWorkflowRun = vi
      .fn<WorkflowRunsClient["getWorkflowRun"]>()
      .mockImplementation(async (workspaceId, runId) => ({
        runId,
        status: workspaceId === "workspace-a" ? "succeeded" : "canceled",
        createdAt: "2026-04-29T00:00:00.000Z",
        finishedAt: "2026-04-29T00:00:01.000Z",
      }));
    const workflowRunsClient = createWorkflowRunsClient({ getWorkflowRun });

    const [workspaceA, workspaceB] = await Promise.all([
      pollWorkflowRun(queryClient, workflowRunsClient, {
        workspaceId: "workspace-a",
        runId: "shared-run",
        maxIterations: 1,
        clock,
        sleep,
      }),
      pollWorkflowRun(queryClient, workflowRunsClient, {
        workspaceId: "workspace-b",
        runId: "shared-run",
        maxIterations: 1,
        clock,
        sleep,
      }),
    ]);

    expect(workspaceA.status).toBe("succeeded");
    expect(workspaceB.status).toBe("canceled");
  });
});
