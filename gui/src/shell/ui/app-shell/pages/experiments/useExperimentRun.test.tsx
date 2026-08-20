/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useExperimentRun } from "./useExperimentRun";

const runtime = vi.hoisted(() => ({
  start: vi.fn(),
  cancel: vi.fn(),
  invalidate: vi.fn(),
  run: undefined as Record<string, unknown> | undefined,
  logs: undefined as { lines: { type: "info"; msg: string }[] } | undefined,
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({ invalidateQueries: runtime.invalidate }),
  };
});

vi.mock("@shell/data/runs/mutations", () => ({
  useStartExperimentRunMutation: () => ({ mutateAsync: runtime.start }),
  useCancelReeRunMutation: () => ({ mutate: runtime.cancel }),
}));
vi.mock("@shell/data/runs/queries", () => ({
  useReeRunQuery: () => ({ data: runtime.run }),
  useReeRunLogsQuery: () => ({ data: runtime.logs }),
}));

describe("useExperimentRun", () => {
  beforeEach(() => {
    runtime.start.mockReset();
    runtime.cancel.mockReset();
    runtime.invalidate.mockReset();
    runtime.run = undefined;
    runtime.logs = undefined;
  });

  it("does not start or cancel without an experiment or active target", () => {
    const { result } = renderHook(() =>
      useExperimentRun({ reeId: "ree-1", experimentName: null, onBeforeRun: vi.fn() }),
    );
    act(() => {
      result.current.startRun();
      result.current.cancelRun();
    });
    expect(runtime.start).not.toHaveBeenCalled();
    expect(runtime.cancel).not.toHaveBeenCalled();
    expect(result.current.runState).toBeNull();
  });

  it("flushes edits, exposes starting state, observes outputs and logs, and cancels", async () => {
    let resolveStart: ((value: unknown) => void) | undefined;
    runtime.start.mockReturnValue(
      new Promise((resolve) => {
        resolveStart = resolve;
      }),
    );
    const onBeforeRun = vi.fn().mockResolvedValue(undefined);
    const { result, rerender } = renderHook(() =>
      useExperimentRun({ reeId: "ree-1", experimentName: "smoke", onBeforeRun }),
    );

    act(() => result.current.startRun());
    expect(result.current.runState).toMatchObject({ status: "created", runId: "" });
    expect(result.current.isRunning).toBe(true);
    await waitFor(() => expect(onBeforeRun).toHaveBeenCalledOnce());
    await act(async () => {
      resolveStart?.({
        reeId: "started-ree",
        run: { runId: "run-1", status: "running", createdAt: "created", startedAt: "started" },
      });
    });
    expect(result.current.runState).toMatchObject({
      reeId: "started-ree",
      runId: "run-1",
      status: "running",
      startedAt: "started",
    });

    runtime.run = {
      status: "succeeded",
      outputs: {
        subject_name: "smoke",
        exit_code: 0,
        verify_exit_code: 0,
        verdict: "pass",
        runtime_path: "runtime.tar",
      },
    };
    runtime.logs = { lines: [{ type: "info", msg: "done" }] };
    rerender();
    expect(result.current.runState).toMatchObject({
      status: "succeeded",
      outputs: {
        subjectName: "smoke",
        exitCode: 0,
        verifyExitCode: 0,
        verdict: "pass",
        runtimePath: "runtime.tar",
      },
      logLines: [{ type: "info", msg: "done" }],
    });
    expect(result.current.isRunning).toBe(false);
    await waitFor(() =>
      expect(runtime.invalidate).toHaveBeenCalledWith({ queryKey: ["ree", "started-ree"] }),
    );
    act(() => result.current.cancelRun());
    expect(runtime.cancel).toHaveBeenCalledWith({ runId: "run-1" });
  });

  it("uses created time and target status while the run query has not loaded", async () => {
    runtime.start.mockResolvedValue({
      reeId: "ree-1",
      run: { runId: "run-2", status: "queued", createdAt: "created", startedAt: "" },
    });
    const { result } = renderHook(() =>
      useExperimentRun({ reeId: "ree-1", experimentName: "smoke", onBeforeRun: vi.fn() }),
    );
    act(() => result.current.startRun());
    await waitFor(() => expect(result.current.runState?.runId).toBe("run-2"));
    expect(result.current.runState).toMatchObject({ status: "queued", startedAt: "created" });
    expect(result.current.runState?.outputs).toBeNull();
    expect(result.current.runState?.failure).toBeNull();
    expect(result.current.runState?.logLines).toEqual([]);
  });

  it("surfaces a typed terminal failure without output data", async () => {
    runtime.start.mockResolvedValue({
      reeId: "ree-1",
      run: { runId: "run-3", status: "running", createdAt: "created" },
    });
    const { result, rerender } = renderHook(() =>
      useExperimentRun({ reeId: "ree-1", experimentName: "smoke", onBeforeRun: vi.fn() }),
    );
    act(() => result.current.startRun());
    await waitFor(() => expect(result.current.runState?.runId).toBe("run-3"));
    runtime.run = {
      status: "failed",
      failure: {
        category: "execution",
        message: "failed",
        retryable: false,
        origin: "executor",
      },
    };
    rerender();
    expect(result.current.runState).toMatchObject({
      status: "failed",
      outputs: null,
      failure: { message: "failed" },
    });
  });

  it("reports start failures and resets state when switching experiments", async () => {
    runtime.start.mockRejectedValue(new Error("offline"));
    let experimentName = "one";
    const { result, rerender } = renderHook(() =>
      useExperimentRun({ reeId: "ree-1", experimentName, onBeforeRun: vi.fn() }),
    );
    act(() => result.current.startRun());
    await waitFor(() => expect(result.current.runState?.error).toBe("Failed to start run"));
    expect(result.current.runState?.status).toBe("failed");
    experimentName = "two";
    rerender();
    expect(result.current.runState).toBeNull();
  });
});
