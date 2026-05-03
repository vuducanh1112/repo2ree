import { describe, expect, it, vi } from "vitest";
import { runSourceWorkspaceAction } from "./sourceAcquisitionLifecycle";

describe("runSourceWorkspaceAction", () => {
  it("falls back to workspace reset when no workflow mode is requested", async () => {
    const resetWorkspaceRequest = vi.fn(async () => {});

    const result = await runSourceWorkspaceAction({
      workspaceClient: { resetWorkspaceRequest },
      workflowRunClient: {
        startWorkflowRun: vi.fn(async () => ({ runId: "run-1" })),
      },
      workspaceId: "active",
      resetPayload: '{"mode":"clear"}',
      runParams: {},
      pollRun: vi.fn(),
    });

    expect(resetWorkspaceRequest).toHaveBeenCalledWith("active", { mode: "clear" });
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
      workspaceClient: {
        resetWorkspaceRequest: vi.fn(async () => {}),
      },
      workflowRunClient: {
        startWorkflowRun: vi.fn(async () => ({ runId: "run-1" })),
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
