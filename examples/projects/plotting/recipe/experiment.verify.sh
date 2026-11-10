#!/usr/bin/env sh
set -eu

awk '/^slope: / { d = $2 - 1.991; ok = d >= -0.005 && d <= 0.005 } END { exit !ok }' result.txt
[ "$(tail -n +2 fit.csv | wc -l)" -eq 10 ]
python3 - <<'EOF'
import struct

with open("figure.png", "rb") as figure:
    head = figure.read(24)
assert head[:8] == b"\x89PNG\r\n\x1a\n", "figure.png is not a PNG"
size = struct.unpack(">II", head[16:24])
assert size == (800, 600), f"figure.png is {size[0]}x{size[1]}, not 800x600"
EOF
