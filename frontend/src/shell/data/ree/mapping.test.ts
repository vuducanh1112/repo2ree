import { describe, expect, it } from "vitest";
import type { ReeDetailDto } from "../../infra/api/apiTypes";
import { mapReeDetailToReeSlices } from "./mapping";

describe("shell/data/ree/mapping", () => {
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
