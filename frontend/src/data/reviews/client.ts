import { useMemo } from "react";
import type {
  ReviewClient,
  ReviewDetail,
  ReviewUploadCompleteRequest,
  ReviewUploadCompleteResponse,
  ReviewUploadInitRequest,
  ReviewUploadInitResponse,
} from "../../domain/review/ReviewTypes";
import type {
  WorkflowRunLogChunk,
  WorkflowRunRecord,
  WorkflowRunStatus,
} from "../../domain/workflow/WorkflowRun";
import { mapRunLogsToLegacy } from "../../infra/api/WorkflowRunsApi";
import { type ApiRuntimeValue, useApiRuntime } from "../apiRuntime";

function createReviewClient(runtime: ApiRuntimeValue): ReviewClient {
  const api = runtime.reviewsApi;

  const mapReviewRun = (run: {
    runId: string;
    status: WorkflowRunStatus;
    createdAt: string;
    startedAt?: string;
    finishedAt?: string;
  }): WorkflowRunRecord => ({
    runId: run.runId,
    status: run.status,
    createdAt: run.createdAt,
    startedAt: run.startedAt,
    finishedAt: run.finishedAt,
  });

  return {
    initReviewUpload: (payload: ReviewUploadInitRequest): Promise<ReviewUploadInitResponse> =>
      api.initReviewUpload(payload),
    uploadReviewBytes: (uploadUrl, data) => api.uploadReviewBytes(uploadUrl, data),
    completeReviewUpload: (
      reviewId,
      payload: ReviewUploadCompleteRequest,
    ): Promise<ReviewUploadCompleteResponse> => api.completeReviewUpload(reviewId, payload),
    getReview: (reviewId): Promise<ReviewDetail> => api.getReview(reviewId),
    acquireSource: async (reviewId) => mapReviewRun(await api.acquireSource(reviewId)),
    createBuildRuntimeRun: async (reviewId, payload) =>
      mapReviewRun(await api.createBuildRuntimeRun(reviewId, payload)),
    createActivationTestRun: async (reviewId, payload) =>
      mapReviewRun(await api.createActivationTestRun(reviewId, payload)),
    getRun: async (reviewId, runId) => mapReviewRun(await api.getRun(reviewId, runId)),
    cancelRun: async (reviewId, runId) => {
      const response = await api.cancelRun(reviewId, runId);
      return response.status;
    },
    listRunLogs: async (reviewId, runId, cursor): Promise<WorkflowRunLogChunk> => {
      const logs = await api.listRunLogs(reviewId, runId, cursor);
      return {
        lines: mapRunLogsToLegacy(logs.entries),
        nextCursor: logs.nextCursor,
        hasMore: logs.hasMore,
      };
    },
  };
}

export function useReviewClient(): ReviewClient {
  const runtime = useApiRuntime();
  return useMemo(() => createReviewClient(runtime), [runtime]);
}
