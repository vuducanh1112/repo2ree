import { describe, expect, it } from "vitest";
import type { FileTreeNode } from "./FileTree";
import { removeWorkspaceFileByPath, upsertWorkspaceFileByPath } from "./fileTreeOps";

describe("fileTreeOps", () => {
  it("upserts files by full path without clobbering duplicate basenames", () => {
    const initial: FileTreeNode[] = [
      {
        id: "dir-scripts",
        name: "scripts",
        type: "folder",
        children: [{ id: "scripts-run", name: "run.sh", type: "file", content: "echo scripts" }],
      },
      {
        id: "dir-tools",
        name: "tools",
        type: "folder",
        children: [{ id: "tools-run", name: "run.sh", type: "file", content: "echo tools" }],
      },
    ];

    const updated = upsertWorkspaceFileByPath(initial, "scripts/run.sh", "echo updated");
    const scriptsFolder = updated.find((node) => node.type === "folder" && node.name === "scripts");
    const toolsFolder = updated.find((node) => node.type === "folder" && node.name === "tools");

    expect(scriptsFolder?.children?.[0].content).toBe("echo updated");
    expect(toolsFolder?.children?.[0].content).toBe("echo tools");
  });

  it("removes only the targeted full path", () => {
    const initial: FileTreeNode[] = [
      {
        id: "dir-scripts",
        name: "scripts",
        type: "folder",
        children: [{ id: "scripts-run", name: "run.sh", type: "file" }],
      },
      {
        id: "dir-tools",
        name: "tools",
        type: "folder",
        children: [{ id: "tools-run", name: "run.sh", type: "file" }],
      },
    ];

    const updated = removeWorkspaceFileByPath(initial, "scripts/run.sh");

    expect(updated.find((node) => node.name === "scripts")).toBeUndefined();
    expect(updated.find((node) => node.name === "tools")).toBeDefined();
  });
});
