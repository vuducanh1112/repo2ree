import { mapReeDraftToRee } from "../../application/review/mapReviewDetailToRee";
import type { Ree } from "../../domain/ree/ReeSpec";
import type { ReviewDetailDto, WorkspaceDetailDto } from ".";

export function mapReviewDraftToRee(review: ReviewDetailDto): Ree {
  return mapReeDraftToRee({
    reeDraft: review.reeDraft,
    fallbackName: review.name,
  });
}

export function mapWorkspaceDraftToRee(workspace: WorkspaceDetailDto): Ree {
  return mapReeDraftToRee({
    reeDraft: workspace.reeDraft,
    fallbackName: workspace.name,
    fallbackOriginUrl: workspace.externalRef ?? "",
  });
}
