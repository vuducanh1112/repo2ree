import { describe, expect, it } from "vitest";
import type { ReeDetailDto } from "../../infra/api/apiTypes";
import { mapReeDetailToReeProject } from "./reeMapping";

function baseRee(overrides: Partial<ReeDetailDto> = {}): ReeDetailDto {
  return {
    reeId: "ree-1",
    name: "workspace-demo",
    status: "draft",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    reeIntent: {},
    files: [],
    reeFiles: [],
    ...overrides,
  };
}

describe("shell/data/ree/reeMapping", () => {
  it("keeps the draft manifest separate from REE files", () => {
    const project = mapReeDetailToReeProject(
      baseRee({
        draftManifest: {
          manifest_state: "draft",
          name: "workspace-demo",
          file_inventory: { workspace: [], overlay: [], artifacts: [] },
        },
        reeFiles: [{ path: "overlay/build.sh", kind: "ree", tag: "Overlay", size: 9 }],
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
        reeFiles: [{ path: "overlay/build.sh", kind: "ree", tag: "Overlay", size: 9 }],
      }),
    );

    expect(project.draftManifest).toBeUndefined();
    expect(project.reeFiles?.map((file) => file.name)).toEqual(["overlay/build.sh"]);
  });
});
