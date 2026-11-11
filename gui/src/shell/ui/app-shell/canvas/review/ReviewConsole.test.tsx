/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */

import type { ReeExperiment } from "@core/ree/ReeSpec";
import { createEmptyReeExperiment } from "@core/ree/ReeSpec";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../../tests/support/renderApp";
import { ReviewEvidence } from "./ReviewEvidence";
import { ReviewStrip } from "./ReviewStrip";
import { useReviewWorkflowModel } from "./useReviewWorkflowModel";

/**
 * The strip and the evidence drawer are two views of one attempt, so they are
 * exercised together: the shell that owns the model renders both, and a test
 * that saw only one of them would not be testing the console a reviewer uses.
 */
function ReviewWorkflowPanel({ experiments }: { experiments: readonly ReeExperiment[] }) {
  const model = useReviewWorkflowModel({ experiments, active: true });
  return (
    <>
      <ReviewStrip model={model} openStep="source" onOpenStep={vi.fn()} />
      <ReviewEvidence model={model} focusStep="source" />
    </>
  );
}

const opened = {
  run_id: "run-review",
  ree_id: "ree-1",
  operation: "source" as const,
  status: "running" as const,
  created_at: "2026-01-01T00:00:00Z",
  started_at: null,
  finished_at: null,
  outputs: { review_id: "review-1" },
  failure: null,
};

describe("ReviewWorkflowPanel", () => {
  it("starts source reproduction with the explicitly selected evidence basis", async () => {
    const user = userEvent.setup();
    const startSourceReview = vi.fn().mockResolvedValue(opened);
    renderWithShell(<ReviewWorkflowPanel experiments={[]} />, {
      reeId: "ree-1",
      services: fakeApiServices({
        ree: {
          listReviews: vi.fn().mockResolvedValue({ reviews: [] }),
          startSourceReview,
        },
      }),
    });
    await user.click(screen.getByRole("radio", { name: "From bundle" }));
    await user.click(screen.getByRole("button", { name: "Reproduce Source" }));
    await waitFor(() =>
      expect(startSourceReview).toHaveBeenCalledWith("ree-1", { basis: "bundled" }),
    );
  });

  it("presents settled source, build, activation, and experiment evidence", async () => {
    const review = {
      review_id: "review-1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:01:00Z",
      status: "succeeded",
      steps: [
        { step: "source", status: "succeeded", failure: null },
        { step: "build_experiment_environment", status: "succeeded", failure: null },
        { step: "activation", status: "succeeded", failure: null },
        { step: "experiments", status: "succeeded", failure: null },
      ],
      source_comparison: {
        basis: "bundled",
        verdict: "identical",
        expected_swhid: "swh:expected",
        observed_swhid: "swh:observed",
      },
      experiment_environment_comparison: {
        basis: "independent",
        verdict: "different",
        expected_artifact_digest: "sha256:a",
        observed_artifact_digest: "sha256:b",
        matched: 2,
        missing_count: 1,
        extra_count: 0,
        version_mismatch_count: 0,
        advisory_count: 0,
        missing: [
          { ecosystem: "pypi", name: "missing-lib", expected_version: "1", observed_version: null },
        ],
        extra: [],
        version_mismatches: [],
      },
      activation_outcome: {
        basis: "independent",
        verdict: "passed",
        experiment_environment_digest: "sha256:b",
        exit_code: 0,
      },
      experiment_comparisons: [
        {
          basis: "independent",
          verdict: "identical",
          experiment_name: "hello",
          verify_script_path: "verify.sh",
          expected_verify_script_digest: "a",
          verify_script_digest: "a",
          expected_verify_exit_code: 0,
          observed_verify_exit_code: 0,
          run_exit_code: 0,
          expected_output_digest: "out",
          observed_output_digest: "out",
          experiment_environment_digest: "sha256:b",
        },
      ],
      failure: null,
    };
    renderWithShell(
      <ReviewWorkflowPanel
        experiments={[
          {
            ...createEmptyReeExperiment(),
            name: "hello",
            runScript: "run.sh",
            verifyScript: "verify.sh",
          },
        ]}
      />,
      {
        reeId: "ree-1",
        services: fakeApiServices({
          ree: { listReviews: vi.fn().mockResolvedValue({ reviews: [review] }) },
        }),
      },
    );
    expect(
      await screen.findByText(/source verified from the REE's own artifacts/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 missing/)).toBeInTheDocument();
    expect(
      screen.getByText(/enters the experiment environment and hands over/i),
    ).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("qualifies bundled evidence and explains matching builds and failed activation", async () => {
    const review = {
      review_id: "review-bundled",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:01:00Z",
      status: "failed",
      steps: [
        { step: "source", status: "succeeded", failure: null },
        { step: "build_experiment_environment", status: "succeeded", failure: null },
        { step: "activation", status: "failed", failure: "activation failed" },
      ],
      source_comparison: {
        basis: "bundled",
        verdict: "identical",
        expected_swhid: null,
        observed_swhid: null,
      },
      experiment_environment_comparison: {
        basis: "bundled",
        verdict: "equivalent",
        expected_artifact_digest: "sha256:same",
        observed_artifact_digest: "sha256:same",
        matched: 3,
        missing_count: 0,
        extra_count: 0,
        version_mismatch_count: 0,
        advisory_count: 2,
        missing: [],
        extra: [],
        version_mismatches: [],
      },
      activation_outcome: {
        basis: "bundled",
        verdict: "failed",
        experiment_environment_digest: "sha256:same",
        exit_code: 1,
      },
      experiment_comparisons: [],
      failure: "activation failed",
    };
    renderWithShell(<ReviewWorkflowPanel experiments={[]} />, {
      reeId: "ree-1",
      services: fakeApiServices({
        ree: { listReviews: vi.fn().mockResolvedValue({ reviews: [review] }) },
      }),
    });
    expect(
      await screen.findByText(/source and experiment environment verified from/),
    ).toBeInTheDocument();
    expect(screen.getByText(/artifact digest: bit-identical/)).toBeInTheDocument();
    expect(screen.getByText(/2 advisory/)).toBeInTheDocument();
    expect(screen.getByText(/did not enter the experiment environment/)).toBeInTheDocument();
    expect(screen.getByText(/exited 1/)).toBeInTheDocument();
  });
});
