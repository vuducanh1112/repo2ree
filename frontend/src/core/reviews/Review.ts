export type ReviewStatus = "running" | "completed" | "failed" | "canceled";
export type SourceComparisonVerdict = "identical" | "different" | "inconclusive";

export interface ReviewSourceComparison {
  expectedSwhid?: string;
  observedSwhid?: string;
  verdict: SourceComparisonVerdict;
}

export interface ReviewAttempt {
  reviewId: string;
  createdAt: string;
  updatedAt: string;
  status: ReviewStatus;
  sourceComparison?: ReviewSourceComparison;
  failure?: string;
}
