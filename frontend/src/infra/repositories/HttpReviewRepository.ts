import type {
  ReviewRepository,
  ReviewUploadCompleteRequest,
  ReviewUploadCompleteResponse,
  ReviewUploadInitRequest,
  ReviewUploadInitResponse,
} from "../../application/ports/ReviewRepository";
import type {
  WorkflowRunLogChunk,
  WorkflowRunRecord,
  WorkflowRunStatus,
} from "../../application/ports/repositoryTypes";
import { ApiClient, mapRunLogsToLegacy, ReviewsApi } from "../api";

interface CreateHttpReviewRepositoryOptions {
  baseUrl?: string;
  headers?: Record<string, string>;
}

function mapReviewRun(run: {
  runId: string;
  status: WorkflowRunStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
}): WorkflowRunRecord {
  return {
    runId: run.runId,
    status: run.status,
    createdAt: run.createdAt,
    startedAt: run.startedAt,
    finishedAt: run.finishedAt,
  };
}

export function createHttpReviewRepository(
  options: CreateHttpReviewRepositoryOptions = {},
): ReviewRepository {
  const api = new ReviewsApi(
    new ApiClient({
      baseUrl: options.baseUrl,
      headers: options.headers,
    }),
  );

  return {
    initReviewUpload: (payload: ReviewUploadInitRequest): Promise<ReviewUploadInitResponse> =>
      api.initReviewUpload(payload),
    uploadReviewBytes: (uploadUrl, data) => api.uploadReviewBytes(uploadUrl, data),
    completeReviewUpload: (
      reviewId,
      payload: ReviewUploadCompleteRequest,
    ): Promise<ReviewUploadCompleteResponse> => api.completeReviewUpload(reviewId, payload),
    getReview: (reviewId) => api.getReview(reviewId),
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
