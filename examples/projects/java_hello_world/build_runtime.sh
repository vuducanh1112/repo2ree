#!/bin/bash
set -euo pipefail

# Run from this script's own directory so the Dockerfile and the produced
# artifact resolve relative to the project, not wherever the build was invoked.
cd "$(dirname "$0")"

IMAGE_NAME="java-hello"
TAG="latest"
OUTPUT_FILE="runtime.tar"

echo "Building Docker image: $IMAGE_NAME:$TAG..."
docker build -t "$IMAGE_NAME:$TAG" .

echo "Exporting image to $OUTPUT_FILE..."
docker save "$IMAGE_NAME:$TAG" -o "$OUTPUT_FILE"

echo "Success! Image exported to $(pwd)/$OUTPUT_FILE"
