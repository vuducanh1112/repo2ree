import type {
  ReviewActivationOutcome,
  ReviewAttempt,
  ReviewBuildComparison,
  ReviewExperimentComparison,
  ReviewPackageDelta,
  ReviewStepState,
} from "@core/reviews/Review";
import type {
  ActivationOutcomeWire,
  BuildComparisonWire,
  ExperimentComparisonWire,
  PackageDeltaWire,
  ReviewRecordWire,
  ReviewStepStateWire,
} from "@shell/infra/api/apiTypes";

export function mapReviewRecord(wire: ReviewRecordWire): ReviewAttempt {
  const comparison = wire.source_comparison;
  return {
    reviewId: wire.review_id,
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
    status: wire.status,
    steps: (wire.steps ?? []).map(mapStepState),
    sourceComparison: comparison
      ? {
          basis: comparison.basis ?? "independent",
          expectedSwhid: comparison.expected_swhid ?? undefined,
          observedSwhid: comparison.observed_swhid ?? undefined,
          verdict: comparison.verdict,
        }
      : undefined,
    buildComparison: wire.build_comparison ? mapBuildComparison(wire.build_comparison) : undefined,
    activationOutcome: wire.activation_outcome
      ? mapActivationOutcome(wire.activation_outcome)
      : undefined,
    experimentComparisons: (wire.experiment_comparisons ?? []).map(mapExperimentComparison),
    failure: wire.failure ?? undefined,
  };
}

function mapExperimentComparison(wire: ExperimentComparisonWire): ReviewExperimentComparison {
  return {
    basis: wire.basis,
    verdict: wire.verdict,
    experimentName: wire.experiment_name,
    verifyScriptPath: wire.verify_script_path ?? "",
    verifyScriptDigest: wire.verify_script_digest ?? undefined,
    expectedVerifyExitCode: wire.expected_verify_exit_code ?? undefined,
    observedVerifyExitCode: wire.observed_verify_exit_code ?? undefined,
    runExitCode: wire.run_exit_code ?? undefined,
    expectedOutputDigest: wire.expected_output_digest ?? undefined,
    observedOutputDigest: wire.observed_output_digest ?? undefined,
    runtimeDigest: wire.runtime_digest ?? undefined,
  };
}

function mapStepState(wire: ReviewStepStateWire): ReviewStepState {
  return { step: wire.step, status: wire.status, failure: wire.failure ?? undefined };
}

function mapBuildComparison(wire: BuildComparisonWire): ReviewBuildComparison {
  return {
    basis: wire.basis ?? "independent",
    verdict: wire.verdict,
    expectedRuntimeDigest: wire.expected_runtime_digest ?? undefined,
    observedRuntimeDigest: wire.observed_runtime_digest ?? undefined,
    matched: wire.matched ?? 0,
    missingCount: wire.missing_count ?? 0,
    extraCount: wire.extra_count ?? 0,
    versionMismatchCount: wire.version_mismatch_count ?? 0,
    advisoryCount: wire.advisory_count ?? 0,
    missing: (wire.missing ?? []).map(mapPackageDelta),
    extra: (wire.extra ?? []).map(mapPackageDelta),
    versionMismatches: (wire.version_mismatches ?? []).map(mapPackageDelta),
  };
}

function mapActivationOutcome(wire: ActivationOutcomeWire): ReviewActivationOutcome {
  return {
    basis: wire.basis,
    verdict: wire.verdict,
    runtimeDigest: wire.runtime_digest ?? undefined,
    runExitCode: wire.run_exit_code ?? undefined,
    verifyExitCode: wire.verify_exit_code ?? undefined,
  };
}

function mapPackageDelta(wire: PackageDeltaWire): ReviewPackageDelta {
  return {
    ecosystem: wire.ecosystem,
    name: wire.name,
    expectedVersion: wire.expected_version ?? undefined,
    observedVersion: wire.observed_version ?? undefined,
  };
}
