#!/usr/bin/env sh
set -eu

echo "container $APPTAINER_CONTAINER" > placement.txt
python source/main.py > result.txt
cat result.txt
echo "ran in $(cat placement.txt)"
