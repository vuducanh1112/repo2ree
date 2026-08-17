import { describe, expect, it } from "vitest";
import { reeDirId, reeFileId, workspaceDirId, workspaceFileId } from "./fileNodeIds";

describe("core/workspace/fileNodeIds", () => {
  it("gives one path four distinct ids, one per inventory and kind", () => {
    const ids = [
      workspaceFileId("build.sh"),
      workspaceDirId("build.sh"),
      reeFileId("build.sh"),
      reeDirId("build.sh"),
    ];

    expect(new Set(ids).size).toBe(ids.length);
  });

  it("keeps the path in the id, so an id survives its neighbours arriving", () => {
    expect(workspaceFileId("src/main.py")).toBe("ws:src/main.py");
    expect(reeFileId("overlay/build.sh")).toBe("ree:overlay/build.sh");
  });
});
