import { mapRawReeDraftToRee } from "../../application/review/mapReviewDetailToRee";
import type { ReeViewState } from "../../domain/ree/ReeViewState";
import type { ReviewDetailDto, WorkspaceDetailDto } from ".";

export function mapReviewDraftToRee(review: ReviewDetailDto): ReeViewState {
  return mapRawReeDraftToRee({
    reeDraft: review.reeDraft,
    fallbackName: review.name,
  });
}

export function mapWorkspaceDetailToRee(workspace: WorkspaceDetailDto): ReeViewState {
  return mapRawReeDraftToRee({
    reeDraft: workspace.reeDraft,
    fallbackName: workspace.name,
    fallbackOriginUrl: workspace.externalRef ?? "",
  });
}
