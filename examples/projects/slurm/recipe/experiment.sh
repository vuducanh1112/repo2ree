#!/usr/bin/env sh
set -eu

# The author's own submission. `srun` waits for the job, passes on its stdout and
# exit code, and takes the job with it when a cancel stops this script.
RESULT=result.txt
rm -f slurm-job.txt

srun --job-name=instant-slurm-hello --nodes=1 --ntasks=1 --time=5 \
  sh source/job.sh source/main.py > "$RESULT"
cat "$RESULT"
echo "ran in Slurm job $(cat slurm-job.txt)"
