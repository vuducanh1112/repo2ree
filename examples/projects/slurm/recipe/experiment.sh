#!/usr/bin/env sh
set -eu

echo "$SLURM_JOB_ID" > slurm-job.txt
python source/main.py > result.txt
cat result.txt
echo "ran in Slurm job $SLURM_JOB_ID"
