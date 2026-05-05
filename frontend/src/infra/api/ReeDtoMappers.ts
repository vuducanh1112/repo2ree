import { mapRawReeDraftToRee } from "../../domain/ree/mapRawReeDraft";
import type { ReeViewState } from "../../domain/ree/ReeViewState";
import type { ReeDetailDto, ReviewDetailDto } from "./apiTypes";

export function mapReviewDraftToRee(review: ReviewDetailDto): ReeViewState {
  return mapRawReeDraftToRee({
    reeDraft: review.reeDraft,
    fallbackName: review.name,
  });
}

export function mapReeDetailToRee(ree: ReeDetailDto): ReeViewState {
  return mapRawReeDraftToRee({
    reeDraft: ree.reeDraft,
    fallbackName: ree.name,
    fallbackOriginUrl: ree.externalRef ?? "",
  });
}
