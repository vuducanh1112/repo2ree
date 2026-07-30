import { describe, expect, it } from "vitest";
import type { FileTreeNode } from "./FileTree";
import {
  findFileByWorkspacePath,
  normalizeWorkspacePath,
  workspaceFileExists,
} from "./fileTreeTraversal";

const files: FileTreeNode[] = [
  {
    id: "src",
    name: "src",
    type: "folder",
    children: [
      { id: "runtime", name: "runtime.tar.gz", type: "file", size: 42 },
      {
        id: "nested",
        name: "nested",
        type: "folder",
        children: [{ id: "other", name: "runtime.tar.gz", type: "file", size: 7 }],
      },
    ],
  },
];

describe("workspace file tree traversal", () => {
  it("normalizes workspace paths without changing their relative target", () => {
    expect(normalizeWorkspacePath("/src//runtime.tar.gz")).toBe("src/runtime.tar.gz");
  });

  it("finds files by exact workspace-relative path", () => {
    expect(findFileByWorkspacePath(files, "src/runtime.tar.gz")?.size).toBe(42);
    expect(findFileByWorkspacePath(files, "src/nested/runtime.tar.gz")?.size).toBe(7);
  });

  it("reports whether a workspace path exists as a file", () => {
    expect(workspaceFileExists(files, "src/runtime.tar.gz")).toBe(true);
    expect(workspaceFileExists(files, "runtime.tar.gz")).toBe(false);
    expect(workspaceFileExists(files, "src")).toBe(false);
  });
});
