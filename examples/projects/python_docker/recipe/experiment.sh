#!/usr/bin/env sh
set -eu

python source/main.py > result.txt
cat result.txt
