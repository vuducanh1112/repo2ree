#!/usr/bin/env sh
set -eu

awk '/^rate: / { d = $2 - 0.1735; ok = d >= -0.0005 && d <= 0.0005 } END { exit !ok }' result.txt
grep -Fqx 'half-life: 4.00 hours' result.txt
python3 source/check_results.py source/data/decay.csv
