#!/usr/bin/env sh
set -eu

# Build the runtime as a SIF. Its root filesystem is this machine's own Python and
# system directories, so nothing is pulled or downloaded.
RUNTIME_ARTIFACT=source/runtime.sif

ROOTFS=$(mktemp -d)
trap 'rm -rf "$ROOTFS"' EXIT

for directory in bin sbin lib lib64 usr; do
  [ -e "/$directory" ] && tar -cf - -C / --exclude=usr/share "$directory" | tar -xf - -C "$ROOTFS"
done

mkdir "$ROOTFS/etc"
: > "$ROOTFS/etc/passwd"
: > "$ROOTFS/etc/group"

apptainer build --force "$RUNTIME_ARTIFACT" "$ROOTFS"
