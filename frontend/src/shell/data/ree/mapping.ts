import { mapRawReeDraftToSlices } from "../../../core/ree/mapRawReeDraft";
import type { ReeDetailDto, ReviewDetailDto } from "../../infra/api/apiTypes";

export function mapReviewDraftToReeSlices(review: ReviewDetailDto) {
  return mapRawReeDraftToSlices({
    reeIntent: review.reeIntent,
    reeSession: review.reeSession,
    fallbackName: review.name,
  });
}

export function mapReeDetailToReeSlices(ree: ReeDetailDto) {
  return mapRawReeDraftToSlices({
    reeIntent: ree.reeIntent,
    reeSession: ree.reeSession,
    fallbackName: ree.name,
    fallbackOriginUrl: ree.externalRef ?? "",
  });
}
