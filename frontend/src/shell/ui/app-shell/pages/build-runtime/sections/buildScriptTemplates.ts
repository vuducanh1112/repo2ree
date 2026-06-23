import type { RuntimeEntry } from "@core/ree/ReeSpec";

interface BuildScriptTemplate {
  key: string;
  label: string;
  hint: string;
  filename: string;
  /** Substrate keys this template applies to, e.g. "container:docker", "local". */
  applicableTo: string[];
  content: string;
}

const BUILD_SCRIPT_TEMPLATES: BuildScriptTemplate[] = [
  // ── Docker ──────────────────────────────────────────────────────────────────
  {
    key: "docker-export",
    label: "Docker build + export tar.gz",
    hint: "Build image, save as runtime.tar.gz",
    filename: "build_runtime.sh",
    applicableTo: ["container:docker"],
    content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"
OUTPUT_FILE="runtime.tar.gz"

echo "[1/3] Building image $IMAGE_TAG"
DOCKER_BUILDKIT=1 docker build --no-cache -t "$IMAGE_TAG" .

echo "[2/3] Exporting image to $OUTPUT_FILE"
docker save "$IMAGE_TAG" | gzip > "$OUTPUT_FILE"

echo "[3/3] Done"
`,
  },
  {
    key: "docker-image-only",
    label: "Docker build (image-ref output)",
    hint: "Build image, reference by tag",
    filename: "build_runtime.sh",
    applicableTo: ["container:docker"],
    content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"

echo "[1/2] Building image $IMAGE_TAG"
DOCKER_BUILDKIT=1 docker build --no-cache -t "$IMAGE_TAG" .

echo "[2/2] Done — image tag: $IMAGE_TAG"
`,
  },
  {
    key: "nix-docker",
    label: "Nix build + Docker load + export",
    hint: "Nix build → Docker load → export",
    filename: "build_runtime.sh",
    applicableTo: ["container:docker"],
    content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"
OUTPUT_FILE="runtime.tar.gz"

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
  // ── Podman ──────────────────────────────────────────────────────────────────
  {
    key: "podman-export",
    label: "Podman build + export tar.gz",
    hint: "Build with Podman, save as OCI tar.gz",
    filename: "build_runtime.sh",
    applicableTo: ["container:podman"],
    content: `#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="ree:latest"
OUTPUT_FILE="runtime.tar.gz"

echo "[1/3] Building image $IMAGE_TAG"
podman build --no-cache -t "$IMAGE_TAG" .

echo "[2/3] Exporting image to $OUTPUT_FILE"
podman save --format=oci-archive "$IMAGE_TAG" | gzip > "$OUTPUT_FILE"

echo "[3/3] Done"
`,
  },
  // ── Apptainer ───────────────────────────────────────────────────────────────
  {
    key: "apptainer-build",
    label: "Apptainer build from def file",
    hint: "Build SIF from Apptainer.def",
    filename: "build_runtime.sh",
    applicableTo: ["container:apptainer"],
    content: `#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="runtime.sif"

echo "[1/2] Building Apptainer SIF from Apptainer.def"
apptainer build "$OUTPUT_FILE" Apptainer.def

echo "[2/2] Done — $OUTPUT_FILE"
`,
  },
  {
    key: "apptainer-docker",
    label: "Pull Docker image → Apptainer SIF",
    hint: "Pull Docker image, convert to SIF",
    filename: "build_runtime.sh",
    applicableTo: ["container:apptainer"],
    content: `#!/usr/bin/env bash
set -euo pipefail

DOCKER_URI="docker://ubuntu:22.04"  # Replace with your image URI
OUTPUT_FILE="runtime.sif"

echo "[1/2] Converting Docker image to Apptainer SIF"
apptainer build "$OUTPUT_FILE" "$DOCKER_URI"

echo "[2/2] Done — $OUTPUT_FILE"
`,
  },
  // ── Local ───────────────────────────────────────────────────────────────────
  {
    key: "conda-pack",
    label: "Conda env pack to tar.gz",
    hint: "Pack conda env to tar.gz",
    filename: "build_runtime.sh",
    applicableTo: ["local"],
    content: `#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="runtime.tar.gz"
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
    hint: "Pack Python venv to tar.gz",
    filename: "build_runtime.sh",
    applicableTo: ["local"],
    content: `#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="runtime.tar.gz"

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
  // ── Custom driver ────────────────────────────────────────────────────────────
  {
    key: "custom-setup",
    label: "Custom one-time setup",
    hint: "One-time setup script for the driver",
    filename: "build_runtime.sh",
    applicableTo: ["custom"],
    content: `#!/usr/bin/env bash
# One-time setup for a custom runtime driver.
# This script prepares anything the driver needs before experiments run.
set -euo pipefail

echo "Setting up custom runtime environment"

# Add your setup commands here, e.g.:
# pip install -r requirements.txt
# conda env create -f environment.yml

echo "Setup complete"
`,
  },
];

/** Return templates relevant to the given substrate, or all when entry is absent/vm. */
export function filterBuildTemplates(entry?: RuntimeEntry | null): BuildScriptTemplate[] {
  if (!entry || entry.kind === "vm") return BUILD_SCRIPT_TEMPLATES;
  const key = entry.kind === "container" ? `container:${entry.engine}` : entry.kind;
  return BUILD_SCRIPT_TEMPLATES.filter((t) => t.applicableTo.includes(key));
}
