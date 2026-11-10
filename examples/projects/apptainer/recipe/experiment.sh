#!/usr/bin/env sh
set -eu

echo "job $SLURM_JOB_ID container $APPTAINER_CONTAINER" > placement.txt
python source/main.py > result.txt
cat result.txt
echo "ran in $(cat placement.txt)"
