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
    expect(mapped.workspaceSourceState.sourceAvailable).toBe(false);
  });

  // A draft's payload is always not_applicable — it describes a sealed bundle's
  // inventory. Reading availability off it left every draft looking sourceless,
  // which disables the steps that need a source (evaluate, build).
  it("reads source availability from evidence standing, not sealed payload", () => {
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
            source: { source_type: "tarball" },
            experiments: [],
          },
          receipts: { experiments: {} },
          contents: { entries: [] },
        },
      },
      status: "draft",
      audit: {
        source: { evidence: "current", payload: "not_applicable", reasons: [] },
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

    expect(mapped.workspaceSourceState.sourceAvailable).toBe(true);
    expect(mapped.workspaceSourceState.sourceIncluded).toBe(false);
    // Every audited step's standing travels into the editor state, so step
    // doneness survives a reload without being remembered per session.
    expect(mapped.stepEvidence).toEqual({
      source: "current",
      evaluation: "missing",
      hardware: "missing",
      runtime: "missing",
      sbom: "missing",
      sbom_cross_check: "missing",
      test_activation: "missing",
    });
  });
});
