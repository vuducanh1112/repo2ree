import type { FileTreeNode } from "../types";

export function walkFileTree<T>(
  nodes: FileTreeNode[],
  visit: (node: FileTreeNode, path: string) => T | null,
  prefix = "",
): T | null {
  for (const node of nodes || []) {
    const path = prefix ? `${prefix}/${node.name}` : node.name;
    const result = visit(node, path);
    if (result !== null) return result;
    if (node.children?.length) {
      const childResult = walkFileTree(node.children, visit, path);
      if (childResult !== null) return childResult;
    }
  }
  return null;
}

export function findVirtualFileByName(nodes: FileTreeNode[], name: string): FileTreeNode | null {
  if (!name) return null;
  const base = name.split("/").pop();
  if (!base) return null;
  return walkFileTree(nodes, (node) => {
    if (node.type === "file" && node.name === base) return node;
    return null;
  });
}

export function listTreeFiles(nodes: FileTreeNode[]): Array<{ path: string; content: string }> {
  const files: Array<{ path: string; content: string }> = [];
  walkFileTree(nodes, (node, path) => {
    if (node.type === "file") files.push({ path, content: node.content ?? "" });
    return null;
  });
  return files;
}
