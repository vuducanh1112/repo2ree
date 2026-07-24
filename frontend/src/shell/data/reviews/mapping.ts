import type { ReviewAttempt } from "@core/reviews/Review";
import type { ReviewRecordWire } from "@shell/infra/api/apiTypes";

export function mapReviewRecord(wire: ReviewRecordWire): ReviewAttempt {
  const comparison = wire.source_comparison;
  return {
    reviewId: wire.review_id,
    createdAt: wire.created_at,
    updatedAt: wire.updated_at,
    status: wire.status,
    sourceComparison: comparison
      ? {
          expectedSwhid: comparison.expected_swhid ?? undefined,
          observedSwhid: comparison.observed_swhid ?? undefined,
          verdict: comparison.verdict,
        }
      : undefined,
    failure: wire.failure ?? undefined,
  };
}
