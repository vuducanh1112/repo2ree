import type { ReeFile } from "@core/ree/ReeTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { describe, expect, it } from "vitest";
import { buildReeFileTree, flattenTreeWithPaths, isLikelyTextFile } from "./filesPageHelpers";

function reeFile(name: string, overrides: Partial<ReeFile> = {}): ReeFile {
  return { id: `id-${name}`, name, content: "", ...overrides } as ReeFile;
}

describe("isLikelyTextFile", () => {
  it("accepts the file types the pipeline authors", () => {
    expect(isLikelyTextFile("ree-scripts/build.sh")).toBe(true);
    expect(isLikelyTextFile("main.py")).toBe(true);
    expect(isLikelyTextFile("artifacts/sbom.json")).toBe(true);
  });

  it("accepts a Dockerfile, which has no extension to go on", () => {
    expect(isLikelyTextFile("Dockerfile")).toBe(true);
    expect(isLikelyTextFile("prod.dockerfile")).toBe(true);
  });

  it("rejects the binaries a run produces, so the viewer never opens them", () => {
    // `runtime.tar` is what the build step emits — the viewer must decline it.
    expect(isLikelyTextFile("python_hello_world/runtime.tar")).toBe(false);
    expect(isLikelyTextFile("source.tar.gz")).toBe(false);
    expect(isLikelyTextFile("LICENSE")).toBe(false);
  });

  it("ignores case", () => {
    expect(isLikelyTextFile("README.MD")).toBe(true);
  });
});

describe("flattenTreeWithPaths", () => {
  const tree: FileTreeNode[] = [
    {
      id: "src",
      name: "src",
      type: "folder",
      children: [
        { id: "main", name: "main.py", type: "file" },
        {
          id: "nested",
          name: "nested",
          type: "folder",
          children: [{ id: "deep", name: "deep.py", type: "file" }],
        },
      ],
    },
    { id: "readme", name: "README.md", type: "file" },
  ];

  it("returns only files, each with its full path", () => {
    expect(flattenTreeWithPaths(tree)).toEqual([
      { node: { id: "main", name: "main.py", type: "file" }, path: "src/main.py" },
      { node: { id: "deep", name: "deep.py", type: "file" }, path: "src/nested/deep.py" },
      { node: { id: "readme", name: "README.md", type: "file" }, path: "README.md" },
    ]);
  });

  it("drops folders entirely, including empty ones", () => {
    const empty: FileTreeNode[] = [{ id: "d", name: "dist", type: "folder", children: [] }];
    expect(flattenTreeWithPaths(empty)).toEqual([]);
  });

  it("prefixes from a caller-supplied root", () => {
    const one: FileTreeNode[] = [{ id: "f", name: "a.py", type: "file" }];
    expect(flattenTreeWithPaths(one, "workspace")[0].path).toBe("workspace/a.py");
  });
});

describe("buildReeFileTree", () => {
  it("nests a flat list of slash-separated names into folders", () => {
    const tree = buildReeFileTree([
      reeFile("ree-scripts/experiments/hello.sh"),
      reeFile("ree-scripts/experiments/hello.verify.sh"),
      reeFile("artifacts/sbom.json"),
    ]);

    expect(tree.map((n) => n.name)).toEqual(["ree-scripts", "artifacts"]);
    const scripts = tree[0].children?.[0];
    expect(scripts?.name).toBe("experiments");
    expect(scripts?.children?.map((n) => n.name)).toEqual(["hello.sh", "hello.verify.sh"]);
  });

  it("reuses a folder rather than creating a sibling with the same name", () => {
    const tree = buildReeFileTree([reeFile("a/one.txt"), reeFile("a/two.txt")]);
    expect(tree).toHaveLength(1);
    expect(tree[0].children).toHaveLength(2);
  });

  it("gives folders path-derived ids, so same-named folders stay distinct", () => {
    const tree = buildReeFileTree([reeFile("a/deep/x.txt"), reeFile("b/deep/y.txt")]);
    const ids = tree.map((root) => root.children?.[0].id);
    expect(ids).toEqual(["ree-dir-a/deep", "ree-dir-b/deep"]);
  });

  it("replaces a file of the same name instead of listing it twice", () => {
    const tree = buildReeFileTree([
      reeFile("ree-scripts/build.sh", { content: "old" }),
      reeFile("ree-scripts/build.sh", { content: "new" }),
    ]);
    expect(tree[0].children).toHaveLength(1);
    expect(tree[0].children?.[0].content).toBe("new");
  });

  it("skips entries with no usable name", () => {
    expect(buildReeFileTree([reeFile(""), reeFile("///")])).toEqual([]);
  });

  it("carries the file's own metadata onto its node", () => {
    const tree = buildReeFileTree([reeFile("notes.md", { size: 42, tag: "authored" } as never)]);
    expect(tree[0]).toMatchObject({ id: "id-notes.md", name: "notes.md", size: 42 });
  });
});
