import type { FileTreeNode } from "../../../core/workspace/FileTree";
import { listTreeFiles, walkFileTree } from "../../../core/workspace/fileTreeTraversal";

export function allFilePaths(nodes: FileTreeNode[]): string[] {
  return listTreeFiles(nodes).map((file) => file.path);
}

export function findFileByPath(nodes: FileTreeNode[], pathStr: string): FileTreeNode | null {
  const normalized = pathStr.replace(/^\//, "").split("/").filter(Boolean).join("/");
  if (!normalized) return null;
  return walkFileTree(nodes, (node, path) => {
    if (node.type === "file" && path === normalized) return node;
    return null;
  });
}

interface ScriptTemplate {
  key: string;
  label: string;
  filename: string;
  content: string;
  suggestedOutput?: string;
}

export function defaultScriptTemplates(
  scriptKind: "build" | "validate" | null,
  runtimeHint: string,
): ScriptTemplate[] {
  if (scriptKind === "validate") {
    const runtimeName =
      runtimeHint && runtimeHint !== "__skipped__" ? runtimeHint : "runtime.tar.gz";
    return [
      {
        key: "activation-smoke",
        label: "Activation smoke test",
        filename: "activation_test.sh",
        content: `#!/usr/bin/env bash
set -euo pipefail

RUNTIME_FILE="${runtimeName}"
IMAGE_TAG="ree:latest"

echo "[1/3] Loading runtime from $RUNTIME_FILE"
docker load < "$RUNTIME_FILE"

echo "[2/3] Running smoke check in $IMAGE_TAG"
docker run --rm --entrypoint "" "$IMAGE_TAG" sh -lc 'echo activation-ok'

echo "[3/3] Runtime activation test passed"
`,
      },
    ];
  }

  if (scriptKind !== "build") return [];

  return [
    {
      key: "docker-export",
      label: "Docker build + export tar.gz",
      filename: "build_runtime.sh",
      suggestedOutput: "runtime.tar.gz",
      content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"
OUTPUT_FILE="runtime.tar.gz"  # Keep this aligned with "Expected output" in the UI

echo "[1/3] Building image $IMAGE_TAG"
DOCKER_BUILDKIT=1 docker build --no-cache -t "$IMAGE_TAG" .

echo "[2/3] Exporting image to $OUTPUT_FILE"
docker save "$IMAGE_TAG" | gzip > "$OUTPUT_FILE"

echo "[3/3] Done"
`,
    },
    {
      key: "docker-image-only",
      label: "Docker build (image ref output)",
      filename: "build_runtime.sh",
      suggestedOutput: "ree:latest",
      content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"  # Keep this aligned with "Expected output" in the UI

echo "[1/2] Building image $IMAGE_TAG"
DOCKER_BUILDKIT=1 docker build --no-cache -t "$IMAGE_TAG" .

echo "[2/2] Done"
echo "Built image: $IMAGE_TAG"
`,
    },
    {
      key: "nix-docker",
      label: "Nix build + Docker load + export",
      filename: "build_runtime.sh",
      suggestedOutput: "runtime.tar.gz",
      content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"
OUTPUT_FILE="runtime.tar.gz"  # Keep this aligned with "Expected output" in the UI

echo "[1/4] Building image artifact with Nix"
DRV_PATH="$(nix build .#dockerImage --print-out-paths --no-link)"

echo "[2/4] Loading image from Nix result"
docker load < "$DRV_PATH"

echo "[3/4] Tagging image as $IMAGE_TAG"
docker tag "$(docker images --format '{{.Repository}}:{{.Tag}}' | head -n 1)" "$IMAGE_TAG"

echo "[4/4] Exporting image to $OUTPUT_FILE"
docker save "$IMAGE_TAG" | gzip > "$OUTPUT_FILE"
`,
    },
    {
      key: "conda-pack",
      label: "Conda env pack to tar.gz",
      filename: "build_runtime.sh",
      suggestedOutput: "runtime.tar.gz",
      content: `#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="runtime.tar.gz"  # Keep this aligned with "Expected output" in the UI
ENV_NAME="ree"

echo "[1/3] Creating conda env from environment.yml"
conda env create -n "$ENV_NAME" -f environment.yml

echo "[2/3] Packing env"
conda run -n "$ENV_NAME" python -m pip install conda-pack
conda run -n "$ENV_NAME" conda-pack -o "$OUTPUT_FILE"

echo "[3/3] Done"
`,
    },
    {
      key: "venv-pip",
      label: "Python venv pack to tar.gz",
      filename: "build_runtime.sh",
      suggestedOutput: "runtime.tar.gz",
      content: `#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="runtime.tar.gz"  # Keep this aligned with "Expected output" in the UI

echo "[1/4] Creating virtual environment"
python -m venv .ree-venv
source .ree-venv/bin/activate

echo "[2/4] Installing dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[3/4] Packing environment"
tar -czf "$OUTPUT_FILE" .ree-venv

echo "[4/4] Done"
`,
    },
  ];
}
