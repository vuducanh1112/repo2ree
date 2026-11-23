import type { ReeFile } from "@core/ree/ReeTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import {
  buildReeFileTree,
  flattenTreeWithPaths,
  WORKSPACE_PATH_PREFIX,
} from "@core/workspace/reeFileTree";
import { useMemo } from "react";

export function useFileConsoleTrees(workspaceFiles: FileTreeNode[], reeFiles: ReeFile[]) {
  const reeTree = useMemo(() => buildReeFileTree(reeFiles), [reeFiles]);
  const workspaceEntries = useMemo(
    () => flattenTreeWithPaths(workspaceFiles, WORKSPACE_PATH_PREFIX),
    [workspaceFiles],
  );
  const reeEntries = useMemo(() => flattenTreeWithPaths(reeTree), [reeTree]);
  const entryById = useMemo(
    () => new Map([...workspaceEntries, ...reeEntries].map((entry) => [entry.node.id, entry])),
    [workspaceEntries, reeEntries],
  );

  return {
    reeTree,
    entryById,
    workspaceFileCount: workspaceEntries.length,
    reeFileCount: reeEntries.length,
  };
}
