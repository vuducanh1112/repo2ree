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

  it("maps an empty record without inventing optional evidence", () => {
    const wire = {
      review_id: "review-empty",
      created_at: "created",
      updated_at: "updated",
      status: "queued",
      steps: null,
      source_comparison: null,
      build_comparison: null,
      activation_outcome: null,
      experiment_comparisons: null,
      failure: null,
    } as unknown as ReviewRecordWire;

    expect(mapReviewRecord(wire)).toEqual({
      reviewId: "review-empty",
      createdAt: "created",
      updatedAt: "updated",
      status: "queued",
      steps: [],
      sourceComparison: undefined,
      buildComparison: undefined,
      activationOutcome: undefined,
      experimentComparisons: [],
      failure: undefined,
    });
  });

  it("defaults absent comparison counts and arrays while retaining failure values", () => {
    const wire = {
      review_id: "review-defaults",
      created_at: "created",
      updated_at: "updated",
      status: "failed",
      steps: [{ step: "build", status: "failed", failure: "build failed" }],
      source_comparison: { basis: "receipt", verdict: "match" },
      build_comparison: { basis: "receipt", verdict: "unknown" },
      activation_outcome: {
        basis: "receipt",
        verdict: "unknown",
        runtime_digest: null,
        run_exit_code: null,
        verify_exit_code: null,
      },
      experiment_comparisons: [
        {
          basis: "receipt",
          verdict: "unknown",
          experiment_name: "experiment",
        },
      ],
      failure: "review failed",
    } as unknown as ReviewRecordWire;
    const mapped = mapReviewRecord(wire);

    expect(mapped.steps[0].failure).toBe("build failed");
    expect(mapped.sourceComparison).toEqual({
      basis: "receipt",
      expectedSwhid: undefined,
      observedSwhid: undefined,
      verdict: "match",
    });
    expect(mapped.buildComparison).toMatchObject({
      basis: "receipt",
      matched: 0,
      missingCount: 0,
      extraCount: 0,
      versionMismatchCount: 0,
      advisoryCount: 0,
      missing: [],
      extra: [],
      versionMismatches: [],
    });
    expect(mapped.activationOutcome).toMatchObject({
      runtimeDigest: undefined,
      runExitCode: undefined,
      verifyExitCode: undefined,
    });
    expect(mapped.experimentComparisons[0]).toMatchObject({
      verifyScriptPath: "",
      expectedVerifyScriptDigest: undefined,
      verifyScriptDigest: undefined,
      expectedVerifyExitCode: undefined,
      observedVerifyExitCode: undefined,
      runExitCode: undefined,
      expectedOutputDigest: undefined,
      observedOutputDigest: undefined,
      runtimeDigest: undefined,
    });
    expect(mapped.failure).toBe("review failed");
  });
});
