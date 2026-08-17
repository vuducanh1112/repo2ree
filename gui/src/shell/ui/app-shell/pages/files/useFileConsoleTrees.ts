import type { ReeFile } from "@core/ree/ReeTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import {
  buildReeFileTree,
  flattenTreeWithPaths,
  WORKSPACE_PATH_PREFIX,
} from "@core/workspace/reeFileTree";
import { useMemo } from "react";

/**
 * The file console's two trees and the one entry map spanning them.
 *
 * The workspace arrives already shaped as a tree (the mapping nests it as it
 * reads the inventory); the REE inventory is flat and is nested here. One
 * `entryById` covers both so a single tab strip and viewer serve either section
 * — which is why the ids the mapping assigns have to be unique across the pair.
 */
export function useFileConsoleTrees(workspaceFiles: FileTreeNode[], reeFiles: ReeFile[]) {
  const reeTree = useMemo(() => buildReeFileTree(reeFiles), [reeFiles]);
  // Workspace entry paths carry the `workspace/` prefix the wire format strips,
  // so an open tab names the file the way the REE root does.
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
