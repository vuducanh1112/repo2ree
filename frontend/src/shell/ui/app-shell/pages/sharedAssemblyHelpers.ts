import type { FileTreeNode } from "@core/workspace/FileTree";
import { listTreeFiles } from "@core/workspace/fileTreeTraversal";

export function allFilePaths(nodes: FileTreeNode[]): string[] {
  return listTreeFiles(nodes).map((file) => file.path);
}

export { findFileByWorkspacePath as findFileByPath } from "@core/workspace/fileTreeTraversal";
