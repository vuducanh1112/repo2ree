#!/usr/bin/env sh
set -eu

awk '/^mean: / { d = $2 - 296.25; ok = d >= -0.01 && d <= 0.01 } END { exit !ok }' result.txt
