import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import type {
  ReviewDetail,
  ReviewUploadCompleteResponse,
  ReviewUploadInitResponse,
} from "../../../core/review/ReviewTypes";
import type {
  ReviewDetailDto,
  ReviewUploadCompleteResponseDto,
  ReviewUploadInitResponseDto,
} from "../../infra/api/apiTypes";
import { mapReviewDraftToReeSlices } from "../ree/mapping";

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
    reeIntent: review.reeIntent,
    reeSession: review.reeSession,
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
