import { describe, expect, it, vi } from "vitest";
import type { ExplorerClock } from "../../../../application/explorer/runtimePorts";
import type { IWorkspaceService } from "../../../../services/workspaceService";
import { pollWorkflowRun } from "./pollWorkflowRun";

const clock: ExplorerClock = {
  nowIso: () => "2026-04-29T00:00:00.000Z",
  nowMillis: () => 1777420800000,
};

describe("pollWorkflowRun", () => {
  it("uses injected sleep between non-terminal polls", async () => {
    const sleep = vi.fn(async () => {});
    const getWorkflowRun = vi
      .fn<IWorkspaceService["getWorkflowRun"]>()
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

    const result = await pollWorkflowRun({ getWorkflowRun } as IWorkspaceService, {
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

  it("uses injected clock when polling is unsupported", async () => {
    const result = await pollWorkflowRun({} as IWorkspaceService, {
      workspaceId: "active",
      runId: "run-1",
      clock,
      sleep: vi.fn(async () => {}),
    });

    expect(result.status).toBe("failed");
    expect(result.ts).toBe("2026-04-29T00:00:00.000Z");
  });
});
