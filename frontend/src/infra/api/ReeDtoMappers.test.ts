import { describe, expect, it } from "vitest";
import type { ReviewDetailDto, WorkspaceDetailDto } from ".";
import { mapReviewDraftToRee, mapWorkspaceDraftToRee } from "./ReeDtoMappers";

describe("reeMappers", () => {
  it("maps review drafts into Ree consistently", () => {
    const review: ReviewDetailDto = {
      reviewId: "rev-1",
      name: "review-demo",
      status: "ready",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
      reeDraft: {
        origin_url: "https://example.org/repo.git",
        source_type: "git",
        _sourceAvailable: true,
        hardware_description: { cpus: { Xeon: { vendor: "Intel", quantity: 2 } } },
      },
      files: [],
      workspaceFiles: [],
    };

    const mapped = mapReviewDraftToRee(review);

    expect(mapped.name).toBe("review-demo");
    expect(mapped.origin_url).toBe("https://example.org/repo.git");
    expect(mapped.hardware_description.cpus.Xeon.vendor).toBe("Intel");
    expect(mapped._sourceAvailable).toBe(true);
  });

  it("falls back to workspace external ref when origin_url is absent", () => {
    const workspace: WorkspaceDetailDto = {
      reeId: "ree-1",
      name: "workspace-demo",
      status: "draft",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
      externalRef: "https://example.org/archive.tar.gz",
      reeDraft: {},
      files: [],
      reeFiles: [],
    };

    const mapped = mapWorkspaceDraftToRee(workspace);

    expect(mapped.name).toBe("workspace-demo");
    expect(mapped.origin_url).toBe("https://example.org/archive.tar.gz");
  });
});
