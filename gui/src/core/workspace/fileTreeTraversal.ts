import type { FileTreeNode } from "./FileTree";

function walkFileTree<T>(
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

export function normalizeWorkspacePath(path: string): string {
  return path.replace(/^\//, "").split("/").filter(Boolean).join("/");
}

export function findFileByWorkspacePath(nodes: FileTreeNode[], path: string): FileTreeNode | null {
  const normalized = normalizeWorkspacePath(path);
  if (!normalized) return null;
  return walkFileTree(nodes, (node, currentPath) => {
    if (node.type === "file" && currentPath === normalized) return node;
    return null;
  });
}

export function workspaceFileExists(nodes: FileTreeNode[], path: string): boolean {
  return !!findFileByWorkspacePath(nodes, path);
}

export function listTreeFiles(nodes: FileTreeNode[]): Array<{ path: string; content: string }> {
  const files: Array<{ path: string; content: string }> = [];
  walkFileTree(nodes, (node, path) => {
    if (node.type === "file") files.push({ path, content: node.content ?? "" });
    return null;
  });
  return files;
}
