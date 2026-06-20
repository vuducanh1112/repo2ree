import type { FileTreeNode } from "@core/workspace/FileTree";

export function countContainerAndNixFiles(files: FileTreeNode[]) {
  let containerCount = 0;
  let nixCount = 0;

  const scan = (nodes: FileTreeNode[]) => {
    for (const node of nodes || []) {
      if (node.type === "folder") scan(node.children ?? []);
      else {
        const lo = node.name.toLowerCase();
        if (
          lo === "dockerfile" ||
          lo === "containerfile" ||
          lo.startsWith("dockerfile.") ||
          lo.startsWith("containerfile.") ||
          lo === "docker-compose.yml" ||
          lo === "docker-compose.yaml"
        ) {
          containerCount += 1;
        }
        if (lo.endsWith(".nix")) nixCount += 1;
      }
    }
  };

  scan(files || []);
  return { containerCount, nixCount };
}

export const EXPECTED_DEP_FILES = [
  {
    label: "requirements.txt",
    hint: "pip — per-package pins",
    color: "#3b82f6",
  },
  { label: "pyproject.toml", hint: "pip / hatch / poetry", color: "#8b5cf6" },
  { label: "environment.yml", hint: "conda + bioconda", color: "#22c55e" },
  { label: "package.json", hint: "npm / yarn dependencies", color: "#dc2626" },
  { label: "Dockerfile", hint: "container environment", color: "#0891b2" },
  { label: "*.nix", hint: "declarative system env", color: "#7c3aed" },
] as const;
