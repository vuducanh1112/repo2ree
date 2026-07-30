import { describe, expect, it } from "vitest";
import { countEnvironmentFiles } from "./environmentFiles";
import type { FileTreeNode } from "./FileTree";

describe("countEnvironmentFiles", () => {
  it("finds container and Nix definitions throughout the tree", () => {
    const files: FileTreeNode[] = [
      { id: "docker", name: "Dockerfile", type: "file" },
      {
        id: "infra",
        name: "infra",
        type: "folder",
        children: [
          { id: "compose", name: "docker-compose.yaml", type: "file" },
          { id: "flake", name: "flake.nix", type: "file" },
          { id: "readme", name: "README.md", type: "file" },
        ],
      },
    ];

    expect(countEnvironmentFiles(files)).toEqual({ containerCount: 2, nixCount: 1 });
  });

  it("recognizes case-insensitive and suffixed container definitions", () => {
    const files: FileTreeNode[] = [
      { id: "one", name: "Containerfile.dev", type: "file" },
      { id: "two", name: "DOCKERFILE.CI", type: "file" },
    ];

    expect(countEnvironmentFiles(files)).toEqual({ containerCount: 2, nixCount: 0 });
  });
});
