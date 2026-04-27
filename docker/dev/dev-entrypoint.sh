#!/bin/sh
set -eu

if [ -S /var/run/docker.sock ]; then
    socket_gid="$(stat -c '%g' /var/run/docker.sock)"
    socket_group="$(getent group "${socket_gid}" | cut -d: -f1 || true)"

    if [ -z "${socket_group}" ]; then
        if getent group docker >/dev/null 2>&1; then
            groupmod -o -g "${socket_gid}" docker
        else
            groupadd -o -g "${socket_gid}" docker
        fi
        socket_group="docker"
    fi

    usermod -a -G "${socket_group}" nixuser
fi

exec gosu nixuser "$@"
