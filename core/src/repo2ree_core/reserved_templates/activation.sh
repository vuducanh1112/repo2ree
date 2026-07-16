#!/usr/bin/env sh
set -eu

# This script fully defines how this runnable executes — it owns entering the
# runtime. For a Docker runtime, for example:
#
# docker run --rm -v "$(pwd):/workspace" -w /workspace my-runtime:latest \
#   python main.py
