#!/bin/sh
set -eu

DATA_ROOT="${WORKSPACE_STORAGE_DIR%/}/.."

mkdir -p "${WORKSPACE_STORAGE_DIR}" "${REVIEWS_STORAGE_DIR}"

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
