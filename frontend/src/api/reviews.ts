import type { ApiClient } from "./client";
import { endpoints } from "./endpoints";
import type {
  ReviewDetailDto,
  ReviewUploadCompleteRequestDto,
  ReviewUploadCompleteResponseDto,
  ReviewUploadInitRequestDto,
  ReviewUploadInitResponseDto,
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
}
