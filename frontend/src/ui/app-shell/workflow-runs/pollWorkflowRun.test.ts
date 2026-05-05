import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { AppShellClock } from "../../../app/bootstrap/ports";
import type { ExecutionRunsClient } from "../../../data/execution-runs/client";
import { pollWorkflowRun } from "./pollWorkflowRun";

const clock: AppShellClock = {
  nowIso: () => "2026-04-29T00:00:00.000Z",
  nowMillis: () => 1777420800000,
};

function createExecutionRunsClient(overrides: Partial<ExecutionRunsClient>): ExecutionRunsClient {
  return {
    getExecutionRun: vi.fn(),
    getExecutionRunLogs: vi.fn(async () => ({ lines: [], hasMore: false })),
    startExecutionRun: vi.fn(),
    cancelExecutionRun: vi.fn(),
    ...overrides,
  } as ExecutionRunsClient;
}

describe("pollWorkflowRun", () => {
  it("stops polling after a run succeeds", async () => {
    const queryClient = new QueryClient();
    const sleep = vi.fn(async () => {});
    const getExecutionRun = vi
      .fn<ExecutionRunsClient["getExecutionRun"]>()
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
    const workflowRunsClient = createExecutionRunsClient({
      getExecutionRun,
      getExecutionRunLogs: vi
        .fn<ExecutionRunsClient["getExecutionRunLogs"]>()
        .mockResolvedValue({ lines: [{ type: "ok", msg: "done" }], hasMore: false }),
    });

    const result = await pollWorkflowRun(queryClient, workflowRunsClient, {
      reeId: "active",
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
    const workflowRunsClient = createExecutionRunsClient({
      getExecutionRun: vi
        .fn<ExecutionRunsClient["getExecutionRun"]>()
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
      reeId: "active",
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
    const workflowRunsClient = createExecutionRunsClient({
      getExecutionRun: vi.fn(async () => {
        throw new Error("backend unavailable");
      }),
    });

    await expect(
      pollWorkflowRun(queryClient, workflowRunsClient, {
        reeId: "active",
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
    const getExecutionRun = vi
      .fn<ExecutionRunsClient["getExecutionRun"]>()
      .mockImplementation(async (reeId, runId) => ({
        runId,
        status: reeId === "workspace-a" ? "succeeded" : "canceled",
        createdAt: "2026-04-29T00:00:00.000Z",
        finishedAt: "2026-04-29T00:00:01.000Z",
      }));
    const workflowRunsClient = createExecutionRunsClient({ getExecutionRun });

    const [workspaceA, workspaceB] = await Promise.all([
      pollWorkflowRun(queryClient, workflowRunsClient, {
        reeId: "workspace-a",
        runId: "shared-run",
        maxIterations: 1,
        clock,
        sleep,
      }),
      pollWorkflowRun(queryClient, workflowRunsClient, {
        reeId: "workspace-b",
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
