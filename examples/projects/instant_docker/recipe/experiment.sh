#!/usr/bin/env sh
set -eu

sh /app/main.sh > result.txt
cat result.txt
