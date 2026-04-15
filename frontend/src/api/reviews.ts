import type { ApiClient } from "./client";
import { endpoints } from "./endpoints";
import type {
  CreateActivationTestRunRequestDto,
  CreateBuildRuntimeRunRequestDto,
  ReviewDetailDto,
  ReviewUploadCompleteRequestDto,
  ReviewUploadCompleteResponseDto,
  ReviewUploadInitRequestDto,
  ReviewUploadInitResponseDto,
  WorkflowLogsDto,
  WorkflowRunDto,
  WorkflowRunStatusDto,
} from "./types";

export class ReviewsApi {
  constructor(private readonly client: ApiClient) {}

  async uploadReviewBytes(uploadUrl: string, data: ArrayBuffer): Promise<void> {
    await this.client.request<Record<string, unknown>>(uploadUrl, {
      method: "PUT",
      headers: {
        "Content-Type": "application/octet-stream",
      },
      body: data,
    });
  }

  async initReviewUpload(
    payload: ReviewUploadInitRequestDto,
  ): Promise<ReviewUploadInitResponseDto> {
    return this.client.request<ReviewUploadInitResponseDto>(endpoints.reviewUploadInit(), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async completeReviewUpload(
    reviewId: string,
    payload: ReviewUploadCompleteRequestDto,
  ): Promise<ReviewUploadCompleteResponseDto> {
    return this.client.request<ReviewUploadCompleteResponseDto>(
      endpoints.reviewUploadComplete(reviewId),
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  async getReview(reviewId: string): Promise<ReviewDetailDto> {
    return this.client.request<ReviewDetailDto>(endpoints.review(reviewId), {
      method: "GET",
    });
  }

  async acquireSource(reviewId: string): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reviewSourceAcquire(reviewId), {
      method: "POST",
    });
  }

  async createBuildRuntimeRun(
    reviewId: string,
    payload: CreateBuildRuntimeRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reviewBuildRuntime(reviewId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createActivationTestRun(
    reviewId: string,
    payload: CreateActivationTestRunRequestDto,
  ): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reviewActivationTest(reviewId), {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getRun(reviewId: string, runId: string): Promise<WorkflowRunDto> {
    return this.client.request<WorkflowRunDto>(endpoints.reviewRun(reviewId, runId), {
      method: "GET",
    });
  }

  async cancelRun(reviewId: string, runId: string): Promise<{ status: WorkflowRunStatusDto }> {
    return this.client.request<{ status: WorkflowRunStatusDto }>(
      endpoints.reviewRunCancel(reviewId, runId),
      { method: "POST" },
    );
  }

  async listRunLogs(reviewId: string, runId: string, cursor?: string): Promise<WorkflowLogsDto> {
    const searchParams = new URLSearchParams();
    if (cursor) searchParams.set("cursor", cursor);
    searchParams.set("limit", "200");
    return this.client.request<WorkflowLogsDto>(
      endpoints.reviewRunLogs(reviewId, runId),
      { method: "GET" },
      searchParams,
    );
  }
}
