#!/bin/sh
# Start the Nix daemon, give the user the checkout's owner and the Docker socket's
# group, mark the container ready, and drop to the user.
set -eu

# Present once the user is set up: a process exec'd into the container before then
# would keep the user's groups as they were. A restarted container sets up again.
READY=/tmp/dev-ready
rm -f "$READY"

# A checkout mounted from a Linux host belongs to that host's user, whose IDs need not
# be 1000: the user takes them on, so what it writes there is the host user's too. A
# checkout that root owns (as Docker Desktop shows a mount) leaves the user as it is.
if [ -d /repo2ree ]; then
    uid=$(stat -c %u /repo2ree)
    gid=$(stat -c %g /repo2ree)
    if [ "$uid" != 0 ] && [ "$uid" != "$(id -u nixuser)" ]; then
        sed -i "s/^nixuser:x:[0-9]*:[0-9]*:/nixuser:x:$uid:$gid:/" /etc/passwd
        sed -i "s/^nixuser:x:[0-9]*:/nixuser:x:$gid:/" /etc/group
        chown -R nixuser: /home/nixuser
    fi
fi

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

touch "$READY"
exec gosu nixuser "$@"
