import { describe, expect, it, vi } from "vitest";
import { runSourceWorkspaceAction } from "./sourceWorkflow";

describe("runSourceWorkspaceAction", () => {
  it("falls back to resetWorkspace when workflow runs are unavailable", async () => {
    const resetWorkspace = vi.fn(async () => {});

    const result = await runSourceWorkspaceAction({
      workspaceService: { resetWorkspace },
      workspaceId: "active",
      resetPayload: '{"mode":"clear"}',
      runParams: { mode: "clear" },
      pollRun: vi.fn(),
    });

    expect(resetWorkspace).toHaveBeenCalledWith("active", '{"mode":"clear"}');
    expect(result.status).toBe("succeeded");
  });

  it("runs remote workflow, streams updates, and finishes the run callback", async () => {
    const onRunStarted = vi.fn();
    const onRunFinished = vi.fn();
    const onUpdateLogs = vi.fn();
    const pollRun = vi.fn(async (_workspaceId, _runId, onUpdate) => {
      onUpdate?.({ lines: [{ type: "info", msg: "working" }], ts: "2026-01-01T00:00:00Z" });
      return { status: "succeeded" as const };
    });

    const result = await runSourceWorkspaceAction({
      workspaceService: {
        resetWorkspace: vi.fn(async () => {}),
        startWorkflowRun: vi.fn(async () => ({ runId: "run-1" })),
        getWorkflowRun: vi.fn(async () => ({ status: "running" as const })),
      },
      workspaceId: "active",
      resetPayload: '{"mode":"download"}',
      runParams: { mode: "download", source: "https://example.org/repo.git" },
      pollRun,
      onRunStarted,
      onRunFinished,
      onUpdateLogs,
    });

    expect(onRunStarted).toHaveBeenCalledWith("source", "run-1");
    expect(onUpdateLogs).toHaveBeenCalled();
    expect(onRunFinished).toHaveBeenCalledWith("source");
    expect(result.status).toBe("succeeded");
  });
});
