#!/bin/bash

INPUT_FILE="runtime.tar.gz"
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
