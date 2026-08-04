import { describe, expect, it } from "vitest";
import type { ReeDocument } from "../../infra/api/apiTypes";
import { mapReeDetailToReeSlices } from "./mapping";

describe("shell/data/ree/mapping", () => {
  it("maps the portable definition into editor slices", () => {
    const ree: ReeDocument = {
      ree_id: "ree-1",
      ree: {
        subject: {
          schema_version: 1,
          definition: {
            name: "workspace-demo",
            catalog: {
              description: "",
              version: "",
              website: "",
              keywords: [],
              contributors: [],
            },
            source: { origin_url: "https://example.org/archive.tar.gz", source_type: "tarball" },
            experiments: [],
          },
          receipts: { experiments: {} },
          contents: { entries: [] },
        },
      },
      status: "draft",
      audit: {
        source: { evidence: "missing", payload: "not_applicable", reasons: [] },
        evaluation: { evidence: "missing", payload: "not_applicable", reasons: [] },
        hardware: { evidence: "missing", payload: "not_applicable", reasons: [] },
        runtime: { evidence: "missing", payload: "not_applicable", reasons: [] },
        sbom: { evidence: "missing", payload: "not_applicable", reasons: [] },
        sbom_cross_check: { evidence: "missing", payload: "not_applicable", reasons: [] },
        test_activation: { evidence: "missing", payload: "not_applicable", reasons: [] },
        experiments: [],
      },
      workspace_files: [],
      ree_files: [],
    };

    const mapped = mapReeDetailToReeSlices(ree);

    expect(mapped.reeSpec.name).toBe("workspace-demo");
    expect(mapped.reeSpec.originUrl).toBe("https://example.org/archive.tar.gz");
  });
});
