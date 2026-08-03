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
      assessment: {
        source: { evidence: "missing", payload: "missing", reasons: [] },
        evaluation: { evidence: "missing", payload: "missing", reasons: [] },
        hardware: { evidence: "missing", payload: "missing", reasons: [] },
        runtime: { evidence: "missing", payload: "missing", reasons: [] },
        sbom: { evidence: "missing", payload: "missing", reasons: [] },
        test_activation: { evidence: "missing", payload: "missing", reasons: [] },
        experiments: [],
        reproducibility: { dependency: 0, environment: 0, machine: 0 },
      },
      workspace_files: [],
      ree_files: [],
    };

    const mapped = mapReeDetailToReeSlices(ree);

    expect(mapped.reeSpec.name).toBe("workspace-demo");
    expect(mapped.reeSpec.originUrl).toBe("https://example.org/archive.tar.gz");
  });
});
