#!/bin/bash
set -euo pipefail

# Run from this script's own directory so the runtime artifact resolves
# relative to the project, not wherever activation was invoked.
cd "$(dirname "$0")"

INPUT_FILE="runtime.tar"
IMAGE_NAME="java-hello"
TAG="latest"

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: $INPUT_FILE not found!"
    exit 1
fi

echo "Loading Docker image from $INPUT_FILE..."
docker load < "$INPUT_FILE"

echo "Running the container..."
docker run --rm "$IMAGE_NAME:$TAG"

echo "Execution complete."
