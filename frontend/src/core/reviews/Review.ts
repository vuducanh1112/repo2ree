import type { ReviewStepKey } from "./reviewDag";

export type ReviewStatus = "running" | "completed" | "failed" | "canceled";
export type SourceComparisonVerdict = "identical" | "different" | "inconclusive";
export type BuildComparisonVerdict = "identical" | "equivalent" | "different" | "inconclusive";

export interface ReviewSourceComparison {
  expectedSwhid?: string;
  observedSwhid?: string;
  verdict: SourceComparisonVerdict;
}

/** One package the author's and the reviewer's runtimes disagree about. */
export interface ReviewPackageDelta {
  ecosystem: string;
  name: string;
  expectedVersion?: string;
  observedVersion?: string;
}

/**
 * How a reviewer's rebuilt runtime compares to the author's. A container build
 * is rarely bit-reproducible, so `identical` (matching runtime digests) is the
 * lucky case and `equivalent` (matching SBOM dependency closures) is the
 * verdict a faithful rebuild normally earns.
 */
export interface ReviewBuildComparison {
  verdict: BuildComparisonVerdict;
  expectedRuntimeDigest?: string;
  observedRuntimeDigest?: string;
  matched: number;
  missingCount: number;
  extraCount: number;
  versionMismatchCount: number;
  advisoryCount: number;
  missing: ReviewPackageDelta[];
  extra: ReviewPackageDelta[];
  versionMismatches: ReviewPackageDelta[];
}

/** The lifecycle state of one step within a review attempt. */
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
  buildComparison?: ReviewBuildComparison;
  failure?: string;
}
