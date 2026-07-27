import type { ReviewStepKey } from "./reviewDag";

export type ReviewStatus = "running" | "completed" | "failed" | "canceled";
export type SourceComparisonVerdict = "identical" | "different" | "inconclusive";
export type BuildComparisonVerdict = "identical" | "equivalent" | "different" | "inconclusive";

/**
 * What the reviewer's side of a comparison was produced from, and therefore
 * what its verdict is worth. `independent` means the outside world produced it
 * — the origin was fetched, the runtime was rebuilt. `bundled` means it came
 * out of the REE itself, so agreement says the shipped bytes match the author's
 * own evidence and nothing more. The two must never be presented alike: a
 * `bundled` verdict is an integrity check, not a reproduction.
 */
export type ReviewEvidenceBasis = "independent" | "bundled";

/** What a step should reproduce from; `auto` lets the backend take the strongest available. */
export type ReviewBasisRequest = "auto" | ReviewEvidenceBasis;

export interface ReviewSourceComparison {
  basis: ReviewEvidenceBasis;
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
  basis: ReviewEvidenceBasis;
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

/**
 * Whether the runtime an attempt certified is inhabitable.
 *
 * Not a comparison — there is no author artifact to reproduce here, so the
 * reviewer's own probe is the whole claim. `basis` is inherited from the steps
 * before it rather than chosen: activation runs in the workspace the build left
 * behind and cannot tell whether the runtime there was rebuilt or unpacked.
 */
export interface ReviewActivationOutcome {
  basis: ReviewEvidenceBasis;
  verdict: ActivationVerdict;
  runtimeDigest?: string;
  runExitCode?: number;
  verifyExitCode?: number;
}

export type ActivationVerdict = "passed" | "failed";

/**
 * What one experiment's reproduction settled. `reproduced` is the ordinary
 * pass: the author's own verify script accepted the reviewer's results.
 * `identical` adds that the declared outputs came out byte for byte the same —
 * more than the author claimed, and never required, since timestamps and seeds
 * land in output files on every honest re-run. `inconclusive` means there was
 * no criterion to meet: the experiment declares no verify script, or the author
 * never ran it themselves.
 */
export type ExperimentVerdict = "identical" | "reproduced" | "different" | "inconclusive";

/**
 * Whether one experiment's result reproduced, judged by the author's own verify
 * script rather than by output bytes.
 *
 * `verifyScriptDigest` is not decoration: a `reproduced` verdict is worth
 * exactly as much as the script that granted it, and those range from a
 * tolerance check against reference values to `test -f results.csv`. Showing
 * which criterion ran is what makes the verdict auditable rather than asserted.
 */
export interface ReviewExperimentComparison {
  basis: ReviewEvidenceBasis;
  verdict: ExperimentVerdict;
  experimentName: string;
  verifyScriptPath: string;
  verifyScriptDigest?: string;
  expectedVerifyExitCode?: number;
  observedVerifyExitCode?: number;
  runExitCode?: number;
  expectedOutputDigest?: string;
  observedOutputDigest?: string;
  runtimeDigest?: string;
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
  activationOutcome?: ReviewActivationOutcome;
  /**
   * One entry per experiment this attempt has reproduced, keyed by name — the
   * one step with more than one subject, so the one step whose evidence is a
   * list. Absent names have not been run; the step's own `ReviewStepState` says
   * only where the lifecycle stands.
   */
  experimentComparisons: ReviewExperimentComparison[];
  failure?: string;
}
