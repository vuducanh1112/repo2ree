/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../tests/support/renderApp";
import {
  useCancelReeRunMutation,
  useStartExperimentRunMutation,
  useStartReeRunMutation,
} from "./mutations";

const run = {
  run_id: "run-1",
  ree_id: "ree-1",
  operation: "build" as const,
  status: "running" as const,
  created_at: "2026-01-01T00:00:00Z",
  started_at: null,
  finished_at: null,
  outputs: {},
  failure: null,
};

describe("run mutations", () => {
  it("starts normal and experiment runs and seeds their query cache", async () => {
    const createBuildRuntimeRun = vi.fn().mockResolvedValue(run);
    const createExperimentRun = vi.fn().mockResolvedValue(run);
    const { Wrapper, queryClient } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ runs: { createBuildRuntimeRun, createExperimentRun } }),
    });
    const { result } = renderHook(
      () => ({ normal: useStartReeRunMutation(), experiment: useStartExperimentRunMutation() }),
      { wrapper: Wrapper },
    );

    await act(() => result.current.normal.mutateAsync({ scriptKey: "build" }));
    await act(() => result.current.experiment.mutateAsync({ experimentName: "hello" }));

    expect(createBuildRuntimeRun).toHaveBeenCalledWith("ree-1", {});
    expect(createExperimentRun).toHaveBeenCalledWith("ree-1", "hello", {});
    expect(queryClient.getQueryData(["step-run", "ree-1", "run-1"])).toMatchObject({
      runId: "run-1",
    });
  });

  it("cancels and invalidates a run", async () => {
    const cancelRun = vi.fn().mockResolvedValue({ status: "canceled" });
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ runs: { cancelRun } }),
    });
    const { result } = renderHook(() => useCancelReeRunMutation(), { wrapper: Wrapper });
    await act(() => result.current.mutateAsync({ runId: "run-1" }));
    expect(cancelRun).toHaveBeenCalledWith("ree-1", "run-1");
  });
});
