import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type {
  ReviewDetail,
  ReviewUploadCompleteResponse,
  ReviewUploadInitResponse,
} from "../../domain/review/ReviewTypes";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type {
  ReviewDetailDto,
  ReviewUploadCompleteResponseDto,
  ReviewUploadInitResponseDto,
} from "../../infra/api/apiTypes";
import { mapReviewDraftToReeSlices } from "../ree/mapping";

type ReeEditorViewModel = ReeSpec & WorkspaceSourceState & ArtifactStatus & EvaluationState;

export function mapReviewUploadInitResponse(
  response: ReviewUploadInitResponseDto,
): ReviewUploadInitResponse {
  return {
    reviewId: response.reviewId,
    uploadUrl: response.uploadUrl,
    uploadToken: response.uploadToken,
  };
}

export function mapReviewDtoToDetail(review: ReviewDetailDto): ReviewDetail {
  return {
    reviewId: review.reviewId,
    name: review.name,
    status: review.status,
    createdAt: review.createdAt,
    updatedAt: review.updatedAt,
    archiveName: review.archiveName,
    reeDraft: review.reeDraft,
    files: review.files,
    workspaceFiles: review.workspaceFiles,
  };
}

export function mapReviewUploadCompleteResponse(
  response: ReviewUploadCompleteResponseDto,
): ReviewUploadCompleteResponse {
  return {
    status: response.status,
    review: mapReviewDtoToDetail(response.review),
  };
}

export function mapReviewDetailToReeEditorViewModel(review: ReviewDetail): ReeEditorViewModel {
  const state = mapReviewDraftToReeSlices(review);
  return {
    ...state.reeSpec,
    ...state.workspaceSourceState,
    ...state.artifactStatus,
    ...state.evaluationState,
  };
}
