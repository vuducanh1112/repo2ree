import { describe, expect, it } from "vitest";
import type { ReeDocument } from "../../infra/api/apiTypes";
import { mapReeDetailToReeProject } from "./reeMapping";

function baseRee(overrides: Partial<ReeDocument> = {}): ReeDocument {
  return {
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
    ...overrides,
  };
}

describe("shell/data/ree/reeMapping", () => {
  it("maps REE files without the removed draft-manifest projection", () => {
    const project = mapReeDetailToReeProject(
      baseRee({
        ree_files: [{ path: "overlay/build.sh", kind: "ree", tag: "Overlay", size: 9 }],
      }),
    );

    expect(project.reeFiles?.map((file) => file.name)).toEqual(["overlay/build.sh"]);
  });
});
