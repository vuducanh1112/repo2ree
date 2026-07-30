import type { FileTreeNode } from "./FileTree";

/**
 * Prune a file tree to the nodes relevant to `query` (case-insensitive
 * substring match on the node name). Files are kept when their name matches; a
 * folder is kept when its own name matches (in which case its whole subtree is
 * preserved so you can browse into it) or when any descendant matches (so the
 * path to every match stays visible). An empty/whitespace query returns the
 * original nodes unchanged.
 */
export function filterFileTree(nodes: FileTreeNode[], query: string): FileTreeNode[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return nodes;

  const prune = (input: FileTreeNode[]): FileTreeNode[] => {
    const kept: FileTreeNode[] = [];
    for (const node of input || []) {
      const selfMatches = node.name.toLowerCase().includes(needle);
      if (node.type === "folder") {
        if (selfMatches) {
          kept.push(node);
          continue;
        }
        const children = prune(node.children || []);
        if (children.length > 0) kept.push({ ...node, children });
      } else if (selfMatches) {
        kept.push(node);
      }
    }
    return kept;
  };

  return prune(nodes);
}
