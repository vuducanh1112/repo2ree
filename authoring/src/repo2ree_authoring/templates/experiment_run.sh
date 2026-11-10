#!/usr/bin/env sh
set -eu

RUN_LOG="results/run.log"

mkdir -p "$(dirname "$RUN_LOG")"
python main.py > "$RUN_LOG"
cat "$RUN_LOG"
