/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../tests/support/fakeApiServices";
import { createShellWrapper } from "../../../../tests/support/renderApp";
import {
  useStartActivationReviewMutation,
  useStartBuildReviewMutation,
  useStartExperimentReviewMutation,
  useStartSourceReviewMutation,
} from "./mutations";

const opened = {
  run_id: "run-1",
  ree_id: "ree-1",
  operation: "source" as const,
  status: "running" as const,
  created_at: "2026-01-01T00:00:00Z",
  started_at: null,
  finished_at: null,
  outputs: { review_id: "review-1" },
  failure: null,
};

describe("review mutations", () => {
  it("starts every review stage against the current REE", async () => {
    const startSourceReview = vi.fn().mockResolvedValue(opened);
    const startBuildReview = vi.fn().mockResolvedValue(opened);
    const startActivationReview = vi.fn().mockResolvedValue(opened);
    const startExperimentReview = vi.fn().mockResolvedValue(opened);
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({
        ree: {
          startSourceReview,
          startBuildReview,
          startActivationReview,
          startExperimentReview,
        },
      }),
    });
    const { result } = renderHook(
      () => ({
        source: useStartSourceReviewMutation(),
        build: useStartBuildReviewMutation(),
        activation: useStartActivationReviewMutation(),
        experiment: useStartExperimentReviewMutation(),
      }),
      { wrapper: Wrapper },
    );

    await expect(act(() => result.current.source.mutateAsync("bundled"))).resolves.toBe("review-1");
    await act(() => result.current.build.mutateAsync({ reviewId: "review-1" }));
    await act(() => result.current.activation.mutateAsync({ reviewId: "review-1" }));
    await act(() =>
      result.current.experiment.mutateAsync({
        reviewId: "review-1",
        experimentName: "hello world",
      }),
    );

    expect(startSourceReview).toHaveBeenCalledWith("ree-1", { basis: "bundled" });
    expect(startBuildReview).toHaveBeenCalledWith("ree-1", "review-1", {
      prune_workspace: false,
      basis: "auto",
    });
    expect(startActivationReview).toHaveBeenCalledWith("ree-1", "review-1");
    expect(startExperimentReview).toHaveBeenCalledWith("ree-1", "review-1", "hello world");
  });

  it("returns no attempt id when an older response does not expose one", async () => {
    const startSourceReview = vi.fn().mockResolvedValue({ ...opened, outputs: {} });
    const { Wrapper } = createShellWrapper({
      reeId: "ree-1",
      services: fakeApiServices({ ree: { startSourceReview } }),
    });
    const { result } = renderHook(() => useStartSourceReviewMutation(), { wrapper: Wrapper });
    await expect(act(() => result.current.mutateAsync("auto"))).resolves.toBeUndefined();
  });
});
