import type { WorkflowRunLogChunk, WorkflowRunRecord, WorkflowRunStatus } from "./repositoryTypes";

export interface ReviewUploadInitRequest {
  fileName: string;
  size: number;
  contentType: string;
}

export interface ReviewUploadInitResponse {
  reviewId: string;
  uploadUrl: string;
  uploadToken: string;
}

export interface ReviewUploadCompleteRequest {
  uploadToken: string;
  archiveName: string;
}

export interface ReviewUploadCompleteResponse {
  status: "ready";
  review: ReviewDetail;
}

export interface ReviewDetail {
  reviewId: string;
  name: string;
  status: "uploading" | "ready";
  createdAt: string;
  updatedAt: string;
  archiveName?: string;
  reeDraft: Record<string, unknown>;
  files?: Array<{ path: string; size?: number }>;
  workspaceFiles?: Array<{ path: string; size?: number }>;
}

export interface ReviewRepository {
  initReviewUpload(payload: ReviewUploadInitRequest): Promise<ReviewUploadInitResponse>;
  uploadReviewBytes(uploadUrl: string, data: ArrayBuffer): Promise<void>;
  completeReviewUpload(
    reviewId: string,
    payload: ReviewUploadCompleteRequest,
  ): Promise<ReviewUploadCompleteResponse>;
  getReview(reviewId: string): Promise<ReviewDetail>;
  acquireSource(reviewId: string): Promise<WorkflowRunRecord>;
  createBuildRuntimeRun(
    reviewId: string,
    payload: {
      build_runtime_script_path: string;
      produced_runtime_path: string;
    },
  ): Promise<WorkflowRunRecord>;
  createActivationTestRun(
    reviewId: string,
    payload: {
      activation_script_path: string;
    },
  ): Promise<WorkflowRunRecord>;
  getRun(reviewId: string, runId: string): Promise<WorkflowRunRecord>;
  cancelRun(reviewId: string, runId: string): Promise<WorkflowRunStatus>;
  listRunLogs(reviewId: string, runId: string, cursor?: string): Promise<WorkflowRunLogChunk>;
}
