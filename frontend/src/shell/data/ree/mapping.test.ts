import { describe, expect, it } from "vitest";
import type { ReeDetailDto, ReviewDetailDto } from "../../infra/api/apiTypes";
import { mapReeDetailToReeSlices, mapReviewDraftToReeSlices } from "./mapping";

describe("shell/data/ree/mapping", () => {
  it("maps review intent+session into explicit slices consistently", () => {
    const review: ReviewDetailDto = {
      reviewId: "rev-1",
      name: "review-demo",
      status: "ready",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
      reeIntent: {
        origin_url: "https://example.org/repo.git",
        source_type: "git",
        catalog_metadata: {
          description: "Review metadata",
          keywords: ["reproducibility"],
          contributors: [{ identifier: "ada", name: "Ada" }],
          corresponding_author_identifier: "ada",
        },
        hardware_description: { cpus: { Xeon: { vendor: "Intel", quantity: 2 } } },
      },
      reeSession: { source_available: true },
      files: [],
      workspaceFiles: [],
    };

    const mapped = mapReviewDraftToReeSlices(review);

    expect(mapped.reeSpec.name).toBe("review-demo");
    expect(mapped.reeSpec.catalog_metadata.description).toBe("Review metadata");
    expect(mapped.reeSpec.catalog_metadata.contributors[0].identifier).toBe("ada");
    expect(mapped.reeSpec.origin_url).toBe("https://example.org/repo.git");
    expect(mapped.reeSpec.hardware_description.cpus.Xeon.vendor).toBe("Intel");
    expect(mapped.workspaceSourceState.sourceAvailable).toBe(true);
  });

  it("falls back to workspace external ref when origin_url is absent", () => {
    const ree: ReeDetailDto = {
      reeId: "ree-1",
      name: "workspace-demo",
      status: "draft",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
      externalRef: "https://example.org/archive.tar.gz",
      reeIntent: {},
      files: [],
      reeFiles: [],
    };

    const mapped = mapReeDetailToReeSlices(ree);

    expect(mapped.reeSpec.name).toBe("workspace-demo");
    expect(mapped.reeSpec.origin_url).toBe("https://example.org/archive.tar.gz");
  });
});
