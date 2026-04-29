import { describe, expect, it, vi } from "vitest";
import { runServiceWorkflow } from "./serviceWorkflow";

describe("runServiceWorkflow", () => {
  it("uses mock execution when workflow runs are unavailable", async () => {
    const createMockResult = vi.fn(async () => ({
      status: "succeeded" as const,
      lines: [],
      ts: "2026-01-01T00:00:00Z",
    }));

    const result = await runServiceWorkflow({
      key: "build",
      runParams: { no_cache: true },
      pollRun: vi.fn(),
      createMockResult,
    });

    expect(createMockResult).toHaveBeenCalled();
    expect(result.status).toBe("succeeded");
  });

  it("runs remote workflows and reports lifecycle callbacks", async () => {
    const onRunStarted = vi.fn();
    const onRunFinished = vi.fn();
    const onUpdateLogs = vi.fn();
    const pollRun = vi.fn(async (_runId, onUpdate) => {
      onUpdate?.({ lines: [{ type: "info", msg: "running" }], ts: "2026-01-01T00:00:00Z" });
      return {
        status: "succeeded" as const,
        lines: [],
        ts: "2026-01-01T00:00:00Z",
      };
    });

    const result = await runServiceWorkflow({
      startWorkflowRun: vi.fn(async () => ({ runId: "run-1" })),
      key: "build",
      runParams: { no_cache: true },
      pollRun,
      createMockResult: vi.fn(),
      onRunStarted,
      onRunFinished,
      onUpdateLogs,
    });

    expect(onRunStarted).toHaveBeenCalledWith("build", "run-1");
    expect(onUpdateLogs).toHaveBeenCalled();
    expect(onRunFinished).toHaveBeenCalledWith("build");
    expect(result.status).toBe("succeeded");
  });
});
