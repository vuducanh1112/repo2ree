import type { ReviewStepKey } from "@core/generated/vocabulary";

export type ReviewStatus = "running" | "completed" | "failed" | "canceled";
export type SourceComparisonVerdict = "identical" | "different" | "inconclusive";
export type ExperimentEnvironmentComparisonVerdict =
  | "identical"
  | "equivalent"
  | "different"
  | "inconclusive";

export type ReviewEvidenceBasis = "independent" | "bundled";

export type ReviewBasisRequest = "auto" | ReviewEvidenceBasis;

export interface ReviewSourceComparison {
  basis: ReviewEvidenceBasis;
  expectedSwhid?: string;
  observedSwhid?: string;
  verdict: SourceComparisonVerdict;
}

export interface ReviewPackageDelta {
  ecosystem: string;
  name: string;
  expectedVersion?: string;
  observedVersion?: string;
}

export interface ReviewBuildComparison {
  basis: ReviewEvidenceBasis;
  verdict: ExperimentEnvironmentComparisonVerdict;
  expectedArtifactDigest?: string;
  observedArtifactDigest?: string;
  matched: number;
  missingCount: number;
  extraCount: number;
  versionMismatchCount: number;
  advisoryCount: number;
  missing: ReviewPackageDelta[];
  extra: ReviewPackageDelta[];
  versionMismatches: ReviewPackageDelta[];
}

export interface ReviewActivationOutcome {
  basis: ReviewEvidenceBasis;
  verdict: ActivationVerdict;
  experimentEnvironmentDigest?: string;
  exitCode?: number;
}

export type ActivationVerdict = "passed" | "failed";

export type ExperimentVerdict = "identical" | "reproduced" | "different" | "inconclusive";

export interface ReviewExperimentComparison {
  basis: ReviewEvidenceBasis;
  verdict: ExperimentVerdict;
  experimentName: string;
  verifyScriptPath: string;
  expectedVerifyScriptDigest?: string;
  verifyScriptDigest?: string;
  expectedVerifyExitCode?: number;
  observedVerifyExitCode?: number;
  runExitCode?: number;
  expectedOutputDigest?: string;
  observedOutputDigest?: string;
  experimentEnvironmentDigest?: string;
}

export interface ReviewStepState {
  step: ReviewStepKey;
  status: ReviewStatus;
  failure?: string;
}

export interface ReviewAttempt {
  reviewId: string;
  createdAt: string;
  updatedAt: string;
  status: ReviewStatus;
  steps: ReviewStepState[];
  sourceComparison?: ReviewSourceComparison;
  experimentEnvironmentComparison?: ReviewBuildComparison;
  activationOutcome?: ReviewActivationOutcome;
  experimentComparisons: ReviewExperimentComparison[];
  failure?: string;
}
