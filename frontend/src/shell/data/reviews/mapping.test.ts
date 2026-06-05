import { describe, expect, it } from "vitest";
import type { ReviewDetail } from "../../../core/review/ReviewTypes";
import type { ReviewDetailDto, ReviewUploadCompleteResponseDto } from "../../infra/api/apiTypes";
import {
  mapReviewDetailToReeEditorViewModel,
  mapReviewDtoToDetail,
  mapReviewUploadCompleteResponse,
  mapReviewUploadInitResponse,
} from "./mapping";

describe("shell/data/reviews/mapping", () => {
  it("maps upload init response to review shape", () => {
    expect(
      mapReviewUploadInitResponse({
        reviewId: "r1",
        uploadUrl: "https://upload.example.org",
        uploadToken: "tok",
        expiresAt: "2026-01-01T00:00:00Z",
      }),
    ).toEqual({
      reviewId: "r1",
      uploadUrl: "https://upload.example.org",
      uploadToken: "tok",
    });
  });

  it("maps review dto and upload complete response", () => {
    const dto: ReviewDetailDto = {
      reviewId: "r1",
      name: "review-name",
      status: "ready",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-02T00:00:00Z",
      archiveName: "review.tar.gz",
      reeIntent: { origin_url: "https://example.org/repo.git" },
      reeSession: {},
      files: [{ path: "out/file.txt", size: 12 }],
      workspaceFiles: [{ path: "src/index.ts", size: 45 }],
    };
    const complete: ReviewUploadCompleteResponseDto = {
      status: "ready",
      review: dto,
    };

    expect(mapReviewDtoToDetail(dto)).toEqual({
      reviewId: "r1",
      name: "review-name",
      status: "ready",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-02T00:00:00Z",
      archiveName: "review.tar.gz",
      reeIntent: { origin_url: "https://example.org/repo.git" },
      reeSession: {},
      files: [{ path: "out/file.txt", size: 12 }],
      workspaceFiles: [{ path: "src/index.ts", size: 45 }],
    });
    expect(mapReviewUploadCompleteResponse(complete).review.reviewId).toBe("r1");
  });

  it("maps review detail to ree editor view model", () => {
    const review: ReviewDetail = {
      reviewId: "r1",
      name: "review-name",
      status: "ready",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-02T00:00:00Z",
      reeIntent: { source_type: "git" },
      reeSession: { source_available: true },
    };

    const view = mapReviewDetailToReeEditorViewModel(review);

    expect(view.name).toBe("review-name");
    expect(view.sourceAvailable).toBe(true);
  });
});
