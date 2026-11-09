#!/usr/bin/env sh
set -eu

# Prove the runtime starts where the experiment will run: in a container, in a job.
srun --job-name=instant-apptainer-activation --nodes=1 --ntasks=1 --time=5 \
  apptainer exec source/runtime.sif \
  python -c "import hashlib; print('activation ok')"
