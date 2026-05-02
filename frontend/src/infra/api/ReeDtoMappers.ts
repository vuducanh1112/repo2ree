import { mapRawReeDraftToRee } from "../../application/review/mapReviewDetailToRee";
import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import type { ReviewDetailDto, WorkspaceDetailDto } from ".";

export function mapReviewDraftToRee(review: ReviewDetailDto): ReeDraftViewModel {
  return mapRawReeDraftToRee({
    reeDraft: review.reeDraft,
    fallbackName: review.name,
  });
}

export function mapWorkspaceDetailToRee(workspace: WorkspaceDetailDto): ReeDraftViewModel {
  return mapRawReeDraftToRee({
    reeDraft: workspace.reeDraft,
    fallbackName: workspace.name,
    fallbackOriginUrl: workspace.externalRef ?? "",
  });
}
