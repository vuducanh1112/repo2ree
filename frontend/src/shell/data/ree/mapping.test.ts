import { describe, expect, it } from "vitest";
import type { ReeDetailDto } from "../../infra/api/apiTypes";
import { mapReeDetailToReeSlices } from "./mapping";

describe("shell/data/ree/mapping", () => {
  it("falls back to workspace external ref when origin_url is absent", () => {
    const ree: ReeDetailDto = {
      ree_id: "ree-1",
      name: "workspace-demo",
      status: "draft",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      external_ref: "https://example.org/archive.tar.gz",
      ree_intent: {},
      files: [],
      ree_files: [],
    };

    const mapped = mapReeDetailToReeSlices(ree);

    expect(mapped.reeSpec.name).toBe("workspace-demo");
    expect(mapped.reeSpec.originUrl).toBe("https://example.org/archive.tar.gz");
  });
});
