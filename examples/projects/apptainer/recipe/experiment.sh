#!/usr/bin/env sh
set -eu

# The author's own submission and container entry: `srun` waits for the job and
# passes on its stdout and exit code; Apptainer binds this directory, so the
# project is at its usual path and the container runs as the user.
RUNTIME_ARTIFACT=source/runtime.sif
RESULT=result.txt
PLACEMENT=placement.txt
rm -f "$PLACEMENT"

srun --job-name=instant-apptainer-hello --nodes=1 --ntasks=1 --time=5 \
  apptainer exec "$RUNTIME_ARTIFACT" \
  sh -c 'echo "job $SLURM_JOB_ID container $APPTAINER_CONTAINER" > "$0"; exec python "$1"' \
  "$PLACEMENT" source/main.py > "$RESULT"
cat "$RESULT"
echo "ran in $(cat "$PLACEMENT")"
