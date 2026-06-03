#!/bin/bash

# Define variables
INPUT_FILE="runtime.tar"
IMAGE_NAME="pandas-hello"
TAG="latest"

# 1. Check if the file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: $INPUT_FILE not found!"
    exit 1
fi

echo "Loading Docker image from $INPUT_FILE..."
# 2. Load the image from the compressed tarball
docker load < "$INPUT_FILE"

echo "Running the container..."
# 3. Run the container and remove it automatically after it finishes (--rm)
docker run --rm "$IMAGE_NAME:$TAG"

echo "Execution complete."
