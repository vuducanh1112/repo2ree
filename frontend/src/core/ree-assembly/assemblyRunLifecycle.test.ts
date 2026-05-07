import { describe, expect, it, vi } from "vitest";
import { runExecutionLifecycle } from "./assemblyRunLifecycle";

describe("runExecutionLifecycle", () => {
  it("runs remote execution runs and reports lifecycle callbacks", async () => {
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

    const result = await runExecutionLifecycle({
      startExecutionRun: vi.fn(async () => ({ runId: "run-1" })),
      request: {
        key: "build",
        scriptKey: "build",
        params: { build_runtime_script_path: "build.sh" },
      },
      pollRun,
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
