#!/bin/sh
set -eu

# The persistent data root is the parent of the reviews dir (the .repo2ree
# volume). REE/workspace state no longer lives here — it's on the workbench
# container volume — so there's no workspace dir to provision. The app
# creates its own subdirs (reviews, upload-staging) at startup; this script
# only needs to make the volume writable by the unprivileged appuser.
DATA_ROOT="${REVIEWS_STORAGE_DIR%/}/.."

mkdir -p "${DATA_ROOT}"

if [ -S /var/run/docker.sock ]; then
    socket_gid="$(stat -c '%g' /var/run/docker.sock)"
    socket_group="$(getent group "${socket_gid}" | cut -d: -f1 || true)"

    if [ -z "${socket_group}" ]; then
        groupmod -o -g "${socket_gid}" docker
        socket_group="docker"
    fi

    usermod -a -G "${socket_group}" appuser
fi

chown -R appuser:appuser "${DATA_ROOT}"

exec gosu appuser "$@"
