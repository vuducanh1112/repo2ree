import { mapRawReeDraftToSlices } from "../../domain/ree/mapRawReeDraft";
import type { ReviewDetail } from "../../domain/review/ReviewTypes";
import {
  createReeEditorViewModel,
  type ReeEditorViewModel,
} from "../ree-editor/reeEditorViewModel";

export function mapReviewDetailToRee(review: ReviewDetail): ReeEditorViewModel {
  return createReeEditorViewModel(
    mapRawReeDraftToSlices({
      reeDraft: review.reeDraft,
      fallbackName: review.name,
    }),
  );
}
