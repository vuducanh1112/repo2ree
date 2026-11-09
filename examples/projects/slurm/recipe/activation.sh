#!/usr/bin/env sh
set -eu

# Prove the runtime starts where the experiment will run: in a job.
srun --job-name=instant-slurm-activation --nodes=1 --ntasks=1 --time=5 \
  sh source/job.sh -c "import hashlib; print('activation ok')"
