/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { describe, expect, it } from "vitest";
import type { ReviewRecordWire } from "../../infra/api/apiTypes";
import { mapReviewRecord } from "./mapping";

describe("mapReviewRecord", () => {
  it("maps a complete review attempt and normalizes nullable evidence", () => {
    const wire = {
      review_id: "review-1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:01:00Z",
      status: "succeeded",
      steps: [{ step: "source", status: "succeeded", failure: null }],
      source_comparison: {
        basis: null,
        verdict: "match",
        expected_swhid: "swh:expected",
        observed_swhid: "swh:observed",
      },
      build_comparison: {
        basis: null,
        verdict: "mismatch",
        expected_runtime_digest: "expected",
        observed_runtime_digest: "observed",
        matched: 2,
        missing_count: 1,
        extra_count: 1,
        version_mismatch_count: 1,
        advisory_count: 0,
        missing: [
          { ecosystem: "pypi", name: "missing", expected_version: "1", observed_version: null },
        ],
        extra: [
          { ecosystem: "pypi", name: "extra", expected_version: null, observed_version: "2" },
        ],
        version_mismatches: [
          { ecosystem: "pypi", name: "changed", expected_version: "1", observed_version: "2" },
        ],
      },
      activation_outcome: {
        basis: "independent",
        verdict: "pass",
        runtime_digest: "digest",
        run_exit_code: 0,
        verify_exit_code: 0,
      },
      experiment_comparisons: [
        {
          basis: "independent",
          verdict: "match",
          experiment_name: "hello",
          verify_script_path: null,
          expected_verify_script_digest: null,
          verify_script_digest: null,
          expected_verify_exit_code: 0,
          observed_verify_exit_code: 0,
          run_exit_code: 0,
          expected_output_digest: "a",
          observed_output_digest: "a",
          runtime_digest: "runtime",
        },
      ],
      failure: null,
    } as unknown as ReviewRecordWire;
    const mapped = mapReviewRecord(wire);

    expect(mapped.sourceComparison?.basis).toBe("independent");
    expect(mapped.buildComparison).toMatchObject({ missingCount: 1, extraCount: 1 });
    expect(mapped.buildComparison?.missing[0]).toEqual({
      ecosystem: "pypi",
      name: "missing",
      expectedVersion: "1",
      observedVersion: undefined,
    });
    expect(mapped.activationOutcome?.verifyExitCode).toBe(0);
    expect(mapped.experimentComparisons[0]).toMatchObject({
      experimentName: "hello",
      verifyScriptPath: "",
    });
  });
});
