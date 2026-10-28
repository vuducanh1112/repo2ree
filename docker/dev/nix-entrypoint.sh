#!/bin/sh
# Start the Nix daemon, give the user the Docker socket's group, and drop to the user.
set -eu

nix-daemon > /tmp/nix-daemon.log 2>&1 &
for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -S /nix/var/nix/daemon-socket/socket ] && break
    sleep 0.5
done

# The socket's group differs by host (root on Docker Desktop, docker on a Linux host).
if [ -S /var/run/docker.sock ]; then
    gid=$(stat -c %g /var/run/docker.sock)
    if group=$(getent group "$gid"); then
        name=${group%%:*}
        members=${group##*:}
        case ",$members," in
            *,nixuser,*) ;;
            ,,) sed -i "s/^$name:\(.*\):$/$name:\1:nixuser/" /etc/group ;;
            *) sed -i "s/^$name:\(.*\)$/$name:\1,nixuser/" /etc/group ;;
        esac
    else
        echo "docker:x:$gid:nixuser" >> /etc/group
    fi
fi

exec gosu nixuser "$@"
