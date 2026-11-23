/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../tests/support/renderApp";
import {
  useStartActivationReviewMutation,
  useStartBuildExperimentEnvironmentReviewMutation,
  useStartExperimentReviewMutation,
  useStartSourceReviewMutation,
} from "./mutations";

const opened = {
  run_id: "run-1",
  ree_id: "ree-1",
  operation: "review_acquire_source" as const,
  status: "running" as const,
  created_at: "2026-01-01T00:00:00Z",
  started_at: null,
  finished_at: null,
  outputs: { review_id: "review-1" },
  failure: null,
};

describe("review mutations", () => {
  it("starts every review stage against the current REE", async () => {
    const reviewAcquireSource = vi.fn().mockResolvedValue(opened);
    const reviewBuildExperimentEnvironment = vi.fn().mockResolvedValue(opened);
    const reviewActivateExperimentEnvironment = vi.fn().mockResolvedValue(opened);
    const reviewRunExperiment = vi.fn().mockResolvedValue(opened);
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({
        ree: {
          reviewAcquireSource,
          reviewBuildExperimentEnvironment,
          reviewActivateExperimentEnvironment,
          reviewRunExperiment,
        },
      }),
    });
    const { result } = renderHook(
      () => ({
        source: useStartSourceReviewMutation(),
        build_experiment_environment: useStartBuildExperimentEnvironmentReviewMutation(),
        activation: useStartActivationReviewMutation(),
        experiment: useStartExperimentReviewMutation(),
      }),
      { wrapper: Wrapper },
    );

    await expect(act(() => result.current.source.mutateAsync("bundled"))).resolves.toBe("review-1");
    await act(() =>
      result.current.build_experiment_environment.mutateAsync({ reviewId: "review-1" }),
    );
    await act(() => result.current.activation.mutateAsync({ reviewId: "review-1" }));
    await act(() =>
      result.current.experiment.mutateAsync({
        reviewId: "review-1",
        experimentName: "hello world",
      }),
    );

    expect(reviewAcquireSource).toHaveBeenCalledWith("ree-1", { basis: "bundled" });
    expect(reviewBuildExperimentEnvironment).toHaveBeenCalledWith("ree-1", "review-1", {
      basis: "auto",
    });
    expect(reviewActivateExperimentEnvironment).toHaveBeenCalledWith("ree-1", "review-1");
    expect(reviewRunExperiment).toHaveBeenCalledWith("ree-1", "review-1", "hello world");
  });

  it("returns no attempt id when an older response does not expose one", async () => {
    const reviewAcquireSource = vi.fn().mockResolvedValue({ ...opened, outputs: {} });
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { reviewAcquireSource } }),
    });
    const { result } = renderHook(() => useStartSourceReviewMutation(), { wrapper: Wrapper });
    await expect(act(() => result.current.mutateAsync("auto"))).resolves.toBeUndefined();
  });
});
