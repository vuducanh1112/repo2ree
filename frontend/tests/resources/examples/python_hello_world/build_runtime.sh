#!/bin/bash

# Define variables
IMAGE_NAME="pandas-hello"
TAG="latest"
OUTPUT_FILE="runtime.tar"

echo "Building Docker image: $IMAGE_NAME:$TAG..."
# Build the image from the current directory
docker build -t "$IMAGE_NAME:$TAG" .

echo "Exporting image to $OUTPUT_FILE..."
# Save the image and compress it into a .tar.gz file
docker save "$IMAGE_NAME:$TAG" -o "$OUTPUT_FILE"

echo "Success! Image exported to $(pwd)/$OUTPUT_FILE"