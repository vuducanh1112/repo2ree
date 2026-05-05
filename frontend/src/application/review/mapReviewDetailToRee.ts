import { mapRawReeDraftToRee } from "../../domain/ree/mapRawReeDraft";
import type { ReeView } from "../../domain/ree/ReeView";
import type { ReviewDetail } from "../../domain/review/ReviewTypes";

export function mapReviewDetailToRee(review: ReviewDetail): ReeView {
  return mapRawReeDraftToRee({
    reeDraft: review.reeDraft,
    fallbackName: review.name,
  });
}
