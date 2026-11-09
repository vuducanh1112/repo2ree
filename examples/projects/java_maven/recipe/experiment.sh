#!/usr/bin/env sh
set -eu

if ! docker image inspect java-hello:latest >/dev/null 2>&1; then
  docker load < source/runtime.tar
fi

docker run --rm -v "$(pwd):/workspace" -w /workspace java-hello:latest java -cp '/app/target/classes:/app/target/dependency/*' com.example.Main > result.txt
cat result.txt
