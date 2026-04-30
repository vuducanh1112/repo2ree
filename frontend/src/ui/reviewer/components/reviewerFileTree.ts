import type { FileTreeNode } from "../../../domain/workspace/FileTree";

export function buildTreeFromPaths(
  files: Array<{ path: string; size?: number }>,
  idPrefix: string,
) {
  const roots: FileTreeNode[] = [];
  for (const file of files) {
    const parts = (file.path || "").split("/").filter(Boolean);
    if (parts.length === 0) continue;

    let cursor = roots;
    let currentPrefix = "";
    for (let index = 0; index < parts.length - 1; index += 1) {
      const part = parts[index];
      currentPrefix = currentPrefix ? `${currentPrefix}/${part}` : part;
      let folder = cursor.find((node) => node.type === "folder" && node.name === part);
      if (!folder) {
        folder = {
          id: `${idPrefix}-dir-${currentPrefix}`,
          name: part,
          type: "folder",
          children: [],
        };
        cursor.push(folder);
      }
      if (!folder.children) folder.children = [];
      cursor = folder.children;
    }

    const fileName = parts[parts.length - 1];
    const fileNode: FileTreeNode = {
      id: `${idPrefix}-file-${file.path}`,
      name: fileName,
      type: "file",
      size: file.size,
      tag: "workspace",
    };
    const existingIndex = cursor.findIndex(
      (node) => node.type === "file" && node.name === fileName,
    );
    if (existingIndex >= 0) {
      cursor[existingIndex] = fileNode;
    } else {
      cursor.push(fileNode);
    }
  }
  return roots;
}
