import type { FileTreeNode } from "./FileTree";

interface UpsertWorkspaceFileOptions {
  tag?: string;
  size?: number;
}

function normalizeWorkspacePath(path: string): string {
  return path
    .split("/")
    .map((segment) => segment.trim())
    .filter(Boolean)
    .join("/");
}

function cloneNode(node: FileTreeNode): FileTreeNode {
  return {
    ...node,
    children: node.children ? node.children.map(cloneNode) : undefined,
  };
}

function sortNodes(nodes: FileTreeNode[]): FileTreeNode[] {
  return [...nodes].sort((left, right) => {
    if (left.type !== right.type) {
      return left.type === "folder" ? -1 : 1;
    }
    return left.name.localeCompare(right.name);
  });
}

export function upsertWorkspaceFileByPath(
  nodes: FileTreeNode[],
  path: string,
  content: string,
  options: UpsertWorkspaceFileOptions = {},
): FileTreeNode[] {
  const normalizedPath = normalizeWorkspacePath(path);
  if (!normalizedPath) {
    return nodes.map(cloneNode);
  }

  const parts = normalizedPath.split("/");
  const roots = nodes.map(cloneNode);
  let cursor = roots;
  let prefix = "";

  for (let i = 0; i < parts.length - 1; i += 1) {
    const segment = parts[i];
    prefix = prefix ? `${prefix}/${segment}` : segment;
    let folder = cursor.find((node) => node.type === "folder" && node.name === segment);
    if (!folder) {
      folder = {
        id: `vf-dir-${prefix}`,
        name: segment,
        type: "folder",
        children: [],
      };
      cursor.push(folder);
    }
    if (!folder.children) {
      folder.children = [];
    }
    cursor = folder.children;
  }

  const name = parts[parts.length - 1];
  const fileNode: FileTreeNode = {
    id: `vf-${normalizedPath}`,
    name,
    type: "file",
    content,
    size: options.size,
    tag: options.tag,
  };
  const existingIndex = cursor.findIndex((node) => node.type === "file" && node.name === name);
  if (existingIndex >= 0) {
    cursor[existingIndex] = fileNode;
  } else {
    cursor.push(fileNode);
  }

  const sortRecursively = (items: FileTreeNode[]): FileTreeNode[] =>
    sortNodes(
      items.map((item) =>
        item.type === "folder" && item.children
          ? { ...item, children: sortRecursively(item.children) }
          : item,
      ),
    );

  return sortRecursively(roots);
}

export function removeWorkspaceFileByPath(nodes: FileTreeNode[], path: string): FileTreeNode[] {
  const normalizedPath = normalizeWorkspacePath(path);
  if (!normalizedPath) {
    return nodes.map(cloneNode);
  }

  const parts = normalizedPath.split("/");

  const removeAtDepth = (items: FileTreeNode[], depth: number): FileTreeNode[] => {
    const segment = parts[depth];

    return items.flatMap((node) => {
      if (node.name !== segment) {
        return [cloneNode(node)];
      }

      if (depth === parts.length - 1) {
        return node.type === "file" ? [] : [cloneNode(node)];
      }

      if (node.type !== "folder" || !node.children) {
        return [cloneNode(node)];
      }

      const nextChildren = removeAtDepth(node.children, depth + 1);
      if (nextChildren.length === 0) {
        return [];
      }

      return [{ ...node, children: nextChildren }];
    });
  };

  return removeAtDepth(nodes, 0);
}
