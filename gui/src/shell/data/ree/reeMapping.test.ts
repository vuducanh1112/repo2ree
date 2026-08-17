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

  it("namespaces node ids per inventory, so one path in both stays two files", () => {
    const project = mapReeDetailToReeProject(
      baseRee({
        workspace_files: [{ path: "build.sh", kind: "generated", size: 9 }],
        ree_files: [{ path: "build.sh", kind: "ree", tag: "Overlay", size: 9 }],
      }),
    );

    expect(project.files.map((file) => file.id)).toEqual(["ws:build.sh"]);
    expect(project.reeFiles?.map((file) => file.id)).toEqual(["ree:build.sh"]);
  });

  it("derives ids from the path, so an insertion does not renumber the rest", () => {
    const later = mapReeDetailToReeProject(
      baseRee({
        ree_files: [
          { path: "artifacts/sbom.json", kind: "ree", tag: "Artifact", size: 2 },
          { path: "overlay/build.sh", kind: "ree", tag: "Overlay", size: 9 },
        ],
      }),
    );

    // The console keys its open tabs by node id and prunes any it can no longer
    // find, so an id that moved with its neighbour's arrival would close tabs.
    expect(later.reeFiles?.map((file) => file.id)).toEqual([
      "ree:artifacts/sbom.json",
      "ree:overlay/build.sh",
    ]);
  });
});
