import type { ReeFile } from "@core/ree/ReeTypes";
import { useMemo } from "react";
import { buildReeFileTree, flattenTreeWithPaths } from "./filesPageHelpers";

export function useReeFileTree(reeFiles: ReeFile[]) {
  const tree = useMemo(() => buildReeFileTree(reeFiles), [reeFiles]);
  const entryById = useMemo(() => {
    const flat = flattenTreeWithPaths(tree);
    return new Map(flat.map((e) => [e.node.id, e]));
  }, [tree]);
  return { tree, entryById };
}
