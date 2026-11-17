#!/usr/bin/env sh
set -eu

# Runs each of the REE's scripts directly: the workbench and run.sh call `sh launch.sh <command>` for every script.
# Whoever runs the REE may put a command in front of each script through REE_LAUNCH_OPTIONS, `nice -n 10` for one.
# shellcheck disable=SC2086
exec ${REE_LAUNCH_OPTIONS:-} "$@"
