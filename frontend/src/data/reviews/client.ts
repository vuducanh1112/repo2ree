import { useMemo } from "react";
import type { ExecutionRun, ExecutionRunLogChunk } from "../../core/execution/ExecutionRun";
import type { ExecutionRunStatus } from "../../core/execution/ExecutionRunStatus";
import type {
  ReviewClient,
  ReviewDetail,
  ReviewUploadCompleteRequest,
  ReviewUploadCompleteResponse,
  ReviewUploadInitRequest,
  ReviewUploadInitResponse,
} from "../../core/review/ReviewTypes";
import { mapRunLogsToLegacy } from "../../infra/api/ExecutionRunsApi";
import { type ApiRuntimeValue, useApiRuntime } from "../apiRuntime";
import {
  mapReviewDtoToDetail,
  mapReviewUploadCompleteResponse,
  mapReviewUploadInitResponse,
} from "./mapping";

function createReviewClient(runtime: ApiRuntimeValue): ReviewClient {
  const api = runtime.reviewsApi;

  const mapReviewRun = (run: {
    runId: string;
    status: ExecutionRunStatus;
    createdAt: string;
    startedAt?: string;
    finishedAt?: string;
  }): ExecutionRun => ({
    runId: run.runId,
    status: run.status,
    createdAt: run.createdAt,
    startedAt: run.startedAt,
    finishedAt: run.finishedAt,
  });

  return {
    initReviewUpload: async (payload: ReviewUploadInitRequest): Promise<ReviewUploadInitResponse> =>
      mapReviewUploadInitResponse(await api.initReviewUpload(payload)),
    uploadReviewBytes: (uploadUrl, data) => api.uploadReviewBytes(uploadUrl, data),
    completeReviewUpload: async (
      reviewId,
      payload: ReviewUploadCompleteRequest,
    ): Promise<ReviewUploadCompleteResponse> =>
      mapReviewUploadCompleteResponse(await api.completeReviewUpload(reviewId, payload)),
    getReview: async (reviewId): Promise<ReviewDetail> =>
      mapReviewDtoToDetail(await api.getReview(reviewId)),
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
    listRunLogs: async (reviewId, runId, cursor): Promise<ExecutionRunLogChunk> => {
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
