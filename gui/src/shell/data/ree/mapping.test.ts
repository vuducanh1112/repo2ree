import { describe, expect, it } from "vitest";
import type { ReeDocument } from "../../infra/api/apiTypes";
import { fixedDeclarations } from "./fixedDeclarations";
import { mapReeDetailToReeSlices } from "./mapping";

describe("shell/data/ree/mapping", () => {
  it("maps the portable definition into editor slices", () => {
    const ree: ReeDocument = {
      ree_id: "ree-1",
      ree: {
        subject: {
          schema_version: 1,
          definition: {
            ...fixedDeclarations,
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
        acquire_source: { evidence: "missing", payload: "not_applicable", reasons: [] },
        evaluate_reproducibility: { evidence: "missing", payload: "not_applicable", reasons: [] },
        observe_hardware: { evidence: "missing", payload: "not_applicable", reasons: [] },
        check_working_environment: {
          evidence: "not_applicable",
          payload: "not_applicable",
          reasons: [],
        },
        build_experiment_environment: {
          evidence: "missing",
          payload: "not_applicable",
          reasons: [],
        },
        generate_sbom: { evidence: "missing", payload: "not_applicable", reasons: [] },
        cross_check_sbom: { evidence: "missing", payload: "not_applicable", reasons: [] },
        activate_experiment_environment: {
          evidence: "missing",
          payload: "not_applicable",
          reasons: [],
        },
        experiments: [],
      },
      steps: {
        steps: [
          {
            key: "acquire_source",
            order: 1,
            label: "Source Acquisition",
            requires: [],
            commands: ["acquire-source"],
            status: "ready",
          },
        ],
        next: "acquire_source",
      },
      workspace_files: [],
      ree_files: [],
    };

    const mapped = mapReeDetailToReeSlices(ree);

    expect(mapped.reeSpec.name).toBe("workspace-demo");
    expect(mapped.reeSpec.originUrl).toBe("https://example.org/archive.tar.gz");
    expect(mapped.workspaceSourceState.sourceAvailable).toBe(false);
    expect(mapped.steps.next).toBe("acquire_source");
    expect(mapped.steps.steps.map((step) => step.status)).toEqual(["ready"]);
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
            ...fixedDeclarations,
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
        acquire_source: { evidence: "current", payload: "not_applicable", reasons: [] },
        evaluate_reproducibility: { evidence: "missing", payload: "not_applicable", reasons: [] },
        observe_hardware: { evidence: "missing", payload: "not_applicable", reasons: [] },
        check_working_environment: {
          evidence: "not_applicable",
          payload: "not_applicable",
          reasons: [],
        },
        build_experiment_environment: {
          evidence: "missing",
          payload: "not_applicable",
          reasons: [],
        },
        generate_sbom: { evidence: "missing", payload: "not_applicable", reasons: [] },
        cross_check_sbom: { evidence: "missing", payload: "not_applicable", reasons: [] },
        activate_experiment_environment: {
          evidence: "missing",
          payload: "not_applicable",
          reasons: [],
        },
        experiments: [],
      },
      steps: { steps: [], next: null },
      workspace_files: [],
      ree_files: [],
    };

    const mapped = mapReeDetailToReeSlices(ree);

    expect(mapped.workspaceSourceState.sourceAvailable).toBe(true);
    expect(mapped.workspaceSourceState.sourceIncluded).toBe(false);
    // Every audited step's standing travels into the editor state, so step
    // doneness survives a reload without being remembered per session.
    expect(mapped.stepEvidence).toEqual({
      acquire_source: "current",
      evaluate_reproducibility: "missing",
      observe_hardware: "missing",
      check_working_environment: "not_applicable",
      build_experiment_environment: "missing",
      generate_sbom: "missing",
      cross_check_sbom: "missing",
      activate_experiment_environment: "missing",
    });
  });
});
