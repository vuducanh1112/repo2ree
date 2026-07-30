import { describe, expect, it } from "vitest";
import type { ReeDocument } from "../../infra/api/apiTypes";
import { mapReeDetailToReeProject } from "./reeMapping";

function baseRee(overrides: Partial<ReeDocument> = {}): ReeDocument {
  return {
    ree_id: "ree-1",
    name: "workspace-demo",
    status: "draft",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    files: [],
    ree_files: [],
    ...overrides,
  };
}

describe("shell/data/ree/reeMapping", () => {
  it("keeps the draft manifest separate from REE files", () => {
    const project = mapReeDetailToReeProject(
      baseRee({
        draft_manifest: {
          manifest_state: "draft",
          name: "workspace-demo",
          file_inventory: { workspace: [], overlay: [], artifacts: [] },
        },
        ree_files: [{ path: "overlay/build.sh", kind: "ree", tag: "Overlay", size: 9 }],
      }),
    );

    expect(project.draftManifest).toEqual({
      manifest_state: "draft",
      name: "workspace-demo",
      file_inventory: { workspace: [], overlay: [], artifacts: [] },
    });
    expect(project.reeFiles?.map((file) => file.name)).toEqual(["overlay/build.sh"]);
  });

  it("leaves draft manifest empty when the API does not provide one", () => {
    const project = mapReeDetailToReeProject(
      baseRee({
        ree_files: [{ path: "overlay/build.sh", kind: "ree", tag: "Overlay", size: 9 }],
      }),
    );

    expect(project.draftManifest).toBeUndefined();
    expect(project.reeFiles?.map((file) => file.name)).toEqual(["overlay/build.sh"]);
  });
});
