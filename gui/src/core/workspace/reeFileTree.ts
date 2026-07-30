import type { ReeFile } from "../ree/ReeTypes";
import type { FileTreeNode } from "./FileTree";

export const FILE_VIEWER_MAX_CHARS = 120_000;
export const FILE_VIEWER_MAX_LINES = 2_000;

const TEXT_FILE_EXTENSIONS = new Set([
  "txt",
  "md",
  "json",
  "yaml",
  "yml",
  "xml",
  "toml",
  "ini",
  "cfg",
  "conf",
  "sh",
  "py",
  "js",
  "ts",
  "tsx",
  "jsx",
  "css",
  "html",
  "csv",
  "log",
  "dockerfile",
]);

export function isLikelyTextFile(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  if (lower === "dockerfile" || lower.endsWith(".dockerfile")) {
    return true;
  }
  const ext = lower.includes(".") ? lower.split(".").pop() || "" : "";
  return TEXT_FILE_EXTENSIONS.has(ext);
}

export interface FlatTreeEntry {
  node: FileTreeNode;
  path: string;
}

export function flattenTreeWithPaths(nodes: FileTreeNode[], prefix = ""): FlatTreeEntry[] {
  const result: FlatTreeEntry[] = [];
  for (const node of nodes || []) {
    const currentPath = prefix ? `${prefix}/${node.name}` : node.name;
    if (node.type === "folder") {
      result.push(...flattenTreeWithPaths(node.children || [], currentPath));
    } else {
      result.push({ node, path: currentPath });
    }
  }
  return result;
}

export function buildReeFileTree(reeFiles: ReeFile[]): FileTreeNode[] {
  const roots: FileTreeNode[] = [];

  function ensureFolder(
    nodes: FileTreeNode[],
    folderName: string,
    folderPath: string,
  ): FileTreeNode {
    const existing = nodes.find((node) => node.type === "folder" && node.name === folderName);
    if (existing) return existing;
    const created: FileTreeNode = {
      id: `ree-dir-${folderPath}`,
      name: folderName,
      type: "folder",
      children: [],
    };
    nodes.push(created);
    return created;
  }

  for (const file of reeFiles || []) {
    const parts = file.name.split("/").filter(Boolean);
    if (parts.length === 0) continue;

    let cursor = roots;
    let folderPath = "";
    for (let idx = 0; idx < parts.length - 1; idx++) {
      const part = parts[idx];
      folderPath = folderPath ? `${folderPath}/${part}` : part;
      const folder = ensureFolder(cursor, part, folderPath);
      folder.children = folder.children ?? [];
      cursor = folder.children;
    }

    const fileName = parts[parts.length - 1];
    const existingFileIdx = cursor.findIndex(
      (node) => node.type === "file" && node.name === fileName,
    );
    const fileNode: FileTreeNode = {
      id: file.id,
      name: fileName,
      type: "file",
      content: file.content,
      size: file.size,
      tag: file.tag,
    };
    if (existingFileIdx >= 0) cursor[existingFileIdx] = fileNode;
    else cursor.push(fileNode);
  }

  return roots;
}
