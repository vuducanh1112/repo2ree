import { mapRawReeDraftToSlices } from "../../domain/ree/mapRawReeDraft";
import type { ReeDetailDto, ReviewDetailDto } from "../../infra/api/apiTypes";

export function mapReviewDraftToReeSlices(review: ReviewDetailDto) {
  return mapRawReeDraftToSlices({
    reeDraft: review.reeDraft,
    fallbackName: review.name,
  });
}

export function mapReeDetailToReeSlices(ree: ReeDetailDto) {
  return mapRawReeDraftToSlices({
    reeDraft: ree.reeDraft,
    fallbackName: ree.name,
    fallbackOriginUrl: ree.externalRef ?? "",
  });
}
