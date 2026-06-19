#!/bin/sh
set -eu

if [ -S /var/run/docker.sock ]; then
    socket_gid="$(stat -c '%g' /var/run/docker.sock)"
    socket_group="$(getent group "${socket_gid}" | cut -d: -f1 || true)"

    if [ -z "${socket_group}" ]; then
        groupmod -o -g "${socket_gid}" docker
        socket_group="docker"
    fi

    usermod -a -G "${socket_group}" appuser
fi

exec gosu appuser "$@"
