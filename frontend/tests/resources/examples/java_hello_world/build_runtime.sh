#!/bin/bash

IMAGE_NAME="java-hello"
TAG="latest"
OUTPUT_FILE="runtime.tar"

echo "Building Docker image: $IMAGE_NAME:$TAG..."
docker build -t "$IMAGE_NAME:$TAG" .

echo "Exporting image to $OUTPUT_FILE..."
docker save "$IMAGE_NAME:$TAG" -o "$OUTPUT_FILE"

echo "Success! Image exported to $(pwd)/$OUTPUT_FILE"
