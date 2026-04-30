import { mapReeDraftToRee } from "../../application/review/mapReviewDetailToRee";
import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import type { ReviewDetailDto, WorkspaceDetailDto } from ".";

export function mapReviewDraftToRee(review: ReviewDetailDto): ReeDraftViewModel {
  return mapReeDraftToRee({
    reeDraft: review.reeDraft,
    fallbackName: review.name,
  });
}

export function mapWorkspaceDraftToRee(workspace: WorkspaceDetailDto): ReeDraftViewModel {
  return mapReeDraftToRee({
    reeDraft: workspace.reeDraft,
    fallbackName: workspace.name,
    fallbackOriginUrl: workspace.externalRef ?? "",
  });
}
