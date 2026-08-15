/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { createEmptyReeExperiment } from "@core/ree/ReeSpec";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { fakeApiServices } from "../../../../../tests/support/fakeApiServices";
import { renderWithShell } from "../../../../../tests/support/renderApp";
import { ReviewConsole } from "./ReviewConsole";

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

describe("ReviewConsole", () => {
  it("starts source reproduction with the explicitly selected evidence basis", async () => {
    const user = userEvent.setup();
    const startSourceReview = vi.fn().mockResolvedValue(opened);
    renderWithShell(<ReviewConsole experiments={[]} />, {
      reeId: "ree-1",
      services: fakeApiServices({
        ree: {
          listReviews: vi.fn().mockResolvedValue({ reviews: [] }),
          startSourceReview,
        },
      }),
    });
    await user.click(screen.getByRole("button", { name: "Expand review controls" }));
    await user.click(screen.getByRole("button", { name: "From bundle" }));
    await user.click(screen.getByRole("button", { name: "Reproduce Source" }));
    await waitFor(() =>
      expect(startSourceReview).toHaveBeenCalledWith("ree-1", { basis: "bundled" }),
    );
  });

  it("presents settled source, build, activation, and experiment evidence", async () => {
    const user = userEvent.setup();
    const review = {
      review_id: "review-1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:01:00Z",
      status: "succeeded",
      steps: [
        { step: "source", status: "succeeded", failure: null },
        { step: "build", status: "succeeded", failure: null },
        { step: "activation", status: "succeeded", failure: null },
        { step: "experiments", status: "succeeded", failure: null },
      ],
      source_comparison: {
        basis: "bundled",
        verdict: "identical",
        expected_swhid: "swh:expected",
        observed_swhid: "swh:observed",
      },
      build_comparison: {
        basis: "independent",
        verdict: "different",
        expected_runtime_digest: "sha256:a",
        observed_runtime_digest: "sha256:b",
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
        runtime_digest: "sha256:b",
        run_exit_code: 0,
        verify_exit_code: 0,
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
          runtime_digest: "sha256:b",
        },
      ],
      failure: null,
    };
    renderWithShell(
      <ReviewConsole
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
    await user.click(screen.getByRole("button", { name: "Expand review controls" }));
    expect(
      await screen.findByText(/source verified from the REE's own artifacts/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/1 missing/)).toBeInTheDocument();
    expect(screen.getByText(/runtime is inhabitable/i)).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
});
