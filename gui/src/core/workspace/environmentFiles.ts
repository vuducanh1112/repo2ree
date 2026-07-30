import type { FileTreeNode } from "./FileTree";

interface EnvironmentFileCounts {
  containerCount: number;
  nixCount: number;
}

export function countEnvironmentFiles(files: FileTreeNode[]): EnvironmentFileCounts {
  let containerCount = 0;
  let nixCount = 0;

  const scan = (nodes: FileTreeNode[]) => {
    for (const node of nodes) {
      if (node.type === "folder") {
        scan(node.children ?? []);
        continue;
      }

      const name = node.name.toLowerCase();
      if (
        name === "dockerfile" ||
        name === "containerfile" ||
        name.startsWith("dockerfile.") ||
        name.startsWith("containerfile.") ||
        name === "docker-compose.yml" ||
        name === "docker-compose.yaml"
      ) {
        containerCount += 1;
      }
      if (name.endsWith(".nix")) nixCount += 1;
    }
  };

  scan(files);
  return { containerCount, nixCount };
}
