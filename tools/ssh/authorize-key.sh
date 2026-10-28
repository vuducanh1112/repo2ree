#!/usr/bin/env bash
# Give a public key SSH access to a dedicated user on this VM. Run it there as root;
# running it again changes nothing.
#
#   authorize-key.sh '<public key>' [user]       user defaults to repo2ree
#   authorize-key.sh --revoke '<key or comment>' [user]
#   authorize-key.sh --list [user]
#
# The user has no password and no sudo. It joins the docker group, which can do
# anything root can, so use a VM dedicated to these runs. Its keys are
# `restrict,pty`: commands and a terminal, but no port, agent or X11 forwarding.
set -euo pipefail

die() { echo "$*" >&2; exit 1; }

case "${1:-}" in
  --list)   action=list   user=${2:-repo2ree} ;;
  --revoke) action=revoke key=${2:?which key?} user=${3:-repo2ree} ;;
  ssh-* | ecdsa-* | sk-*) action=add key=$1 user=${2:-repo2ree} ;;
  *) sed -n '5,7s/^# //p' "$0"; exit 2 ;;
esac
[ "$(id -u)" = 0 ] || die "Run this as root."
if [ $action = add ]; then
  ssh-keygen -lf - <<<"$key" >/dev/null || die "That is not a single public key."
fi

if ! id "$user" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$user"
  # '*' matches no password. Unlike '!', sshd does not treat it as a locked account.
  usermod --password '*' "$user"
  echo "Created user $user"
fi
home=$(getent passwd "$user" | cut -d: -f6)
auth=$home/.ssh/authorized_keys
mkdir -p "$home/.ssh"
touch "$auth"
chmod 700 "$home/.ssh"
chmod 600 "$auth"
chown -R "$user:" "$home/.ssh"

# Every line of $auth except those containing $1.
without() { grep -vF -- "$1" "$auth" || true; }

case $action in
  list)
    ssh-keygen -lf "$auth"
    ;;
  revoke)
    kept=$(without "$key")
    printf '%s' "${kept:+$kept$'\n'}" >"$auth"
    echo "Removed every key of $user matching: $key"
    ;;
  add)
    read -r _ blob _ <<<"$key"
    # Replace any earlier line for this key, so its options are always the current ones.
    kept=$(without "$blob")
    printf '%srestrict,pty %s\n' "${kept:+$kept$'\n'}" "$key" >"$auth"
    echo "Authorized key for $user"
    if getent group docker >/dev/null; then
      usermod -aG docker "$user"
    else
      echo "No docker group yet: install Docker, then run this again." >&2
    fi
    command -v git >/dev/null || echo "No git: install it, since e2e runs keep a clone here." >&2
    echo
    echo "Host key fingerprints, to check the first connection against:"
    for pub in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$pub"; done
    ;;
esac
