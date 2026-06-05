import { mapRawReeIntentToSlices } from "../../../core/ree/mapRawReeIntent";
import type { ReeDetailDto, ReviewDetailDto } from "../../infra/api/apiTypes";

export function mapReviewDraftToReeSlices(review: ReviewDetailDto) {
  return mapRawReeIntentToSlices({
    reeIntent: review.reeIntent,
    reeSession: review.reeSession,
    fallbackName: review.name,
  });
}

export function mapReeDetailToReeSlices(ree: ReeDetailDto) {
  return mapRawReeIntentToSlices({
    reeIntent: ree.reeIntent,
    reeSession: ree.reeSession,
    fallbackName: ree.name,
    fallbackOriginUrl: ree.externalRef ?? "",
  });
}
