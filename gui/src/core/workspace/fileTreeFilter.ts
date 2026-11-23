import type { FileTreeNode } from "./FileTree";

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
