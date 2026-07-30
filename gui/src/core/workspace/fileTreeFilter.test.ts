import { describe, expect, it } from "vitest";
import type { FileTreeNode } from "./FileTree";
import { filterFileTree } from "./fileTreeFilter";

const tree: FileTreeNode[] = [
  {
    id: "src",
    name: "src",
    type: "folder",
    children: [
      { id: "main", name: "main.py", type: "file" },
      { id: "readme", name: "README.md", type: "file" },
      {
        id: "tests",
        name: "tests",
        type: "folder",
        children: [{ id: "test-main", name: "test_main.py", type: "file" }],
      },
    ],
  },
  { id: "docker", name: "Dockerfile", type: "file" },
];

describe("filterFileTree", () => {
  it("returns the original nodes for an empty or whitespace query", () => {
    expect(filterFileTree(tree, "")).toBe(tree);
    expect(filterFileTree(tree, "   ")).toBe(tree);
  });

  it("keeps matching files and the folders that lead to them", () => {
    const result = filterFileTree(tree, "main");
    expect(result).toHaveLength(1);
    const src = result[0];
    expect(src.name).toBe("src");
    // README is dropped; tests/ is kept because test_main.py matches.
    expect(src.children?.map((c) => c.name)).toEqual(["main.py", "tests"]);
    expect(src.children?.find((c) => c.name === "tests")?.children?.map((c) => c.name)).toEqual([
      "test_main.py",
    ]);
  });

  it("matches case-insensitively on file names", () => {
    expect(filterFileTree(tree, "dockerfile")).toEqual([
      { id: "docker", name: "Dockerfile", type: "file" },
    ]);
  });

  it("keeps a folder's entire subtree when the folder name itself matches", () => {
    const result = filterFileTree(tree, "src");
    expect(result).toHaveLength(1);
    expect(result[0]).toBe(tree[0]);
  });

  it("returns no nodes when nothing matches", () => {
    expect(filterFileTree(tree, "nonexistent")).toEqual([]);
  });
});
