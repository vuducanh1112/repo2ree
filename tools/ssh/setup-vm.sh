#!/usr/bin/env bash
# Give a VM a dedicated e2e user that your SSH agent can log in as, or take it away again.
#
#   tools/ssh/setup-vm.sh [--confirm] <admin login> [vm user]
#   tools/ssh/setup-vm.sh --revoke <admin login> [vm user]
#
# <admin login> is how you reach the VM today with root or sudo rights, such as
# ubuntu@203.0.113.7 or an alias from ~/.ssh/config. Setting up
#   1. makes the key ~/.ssh/repo2ree-<host>, unless it exists (set a passphrase),
#   2. loads it into your agent (--confirm: the agent asks you before each use),
#   3. copies authorize-key.sh to a temporary directory on the VM and runs it as
#      root, which creates the vm user (default repo2ree) and authorizes the key,
#   4. logs in as that user with the key, to prove it works.
# Revoking removes the key from the VM, checks it no longer logs in, then drops
# it from your agent and deletes it here. Setting up again makes a new one.
#
# Run it on your own computer, not in the dev container: the private key stays
# here, and the container uses it through the agent that VS Code forwards.
#
# Examples:
#   tools/ssh/setup-vm.sh ubuntu@203.0.113.7             user repo2ree, via your admin login
#   tools/ssh/setup-vm.sh my-vm                          the same, via a ~/.ssh/config alias
#   tools/ssh/setup-vm.sh ubuntu@203.0.113.7 e2e         a user named e2e
#   tools/ssh/setup-vm.sh --confirm ubuntu@203.0.113.7   needs 1Password or Secretive on macOS
#   tools/ssh/setup-vm.sh --revoke ubuntu@203.0.113.7
#   tools/ssh/setup-vm.sh --revoke ubuntu@203.0.113.7 e2e
# Revoke with the admin login you set up with: the key is named after its host
# part, so ubuntu@203.0.113.7 and my-vm are different VMs here.
set -euo pipefail

action=setup add=(ssh-add)
case "${1:-}" in
  --confirm) add=(ssh-add -c); shift ;;
  --revoke) action=revoke; shift ;;
esac
[ $# -ge 1 ] || { sed -n '4,5s/^# //p' "$0"; exit 2; }
admin=$1 user=${2:-repo2ree}
host=${admin#*@}
key=~/.ssh/repo2ree-${host//[^A-Za-z0-9.-]/_}
here=$(cd "$(dirname "$0")" && pwd)

# One admin login for every step: later connections reuse the first. Its socket path
# must stay short (about 104 bytes), which macOS's $TMPDIR can exceed.
control=$(mktemp -d /tmp/repo2ree-ssh.XXXXXX)
via=(-o ControlMaster=auto -o ControlPath="$control/admin" -o ControlPersist=60)
trap 'ssh "${via[@]}" -O exit "$admin" 2>/dev/null || true; rm -rf "$control"' EXIT

# Run authorize-key.sh with these arguments on the VM as root, leaving no copy behind.
authorize_key() {
  local tmp
  tmp=$(ssh "${via[@]}" "$admin" mktemp -d)
  scp -q "${via[@]}" "$here/authorize-key.sh" "$admin:$tmp/"
  ssh "${via[@]}" -t "$admin" "\$(test \"\$(id -u)\" = 0 || echo sudo) bash $tmp/authorize-key.sh $(printf '%q ' "$@");
    status=\$?; rm -rf $tmp; exit \$status"
}

# Whether the VM accepts the key as the vm user.
logs_in() {
  ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$key" -l "$user" "$host" "$@"
}

if [ $action = setup ]; then
  [ -e "$key" ] || ssh-keygen -t ed25519 -C "repo2ree-$user@$host" -f "$key"
  "${add[@]}" "$key"
  echo ">> Authorizing $key.pub for $user on $host"
  authorize_key "$(cat "$key.pub")" "$user"
  echo ">> Logging in as $user with the key"
  # shellcheck disable=SC2016  # expands on the VM
  logs_in 'echo "Logged in as $(id -un) on $(hostname)"'
  echo ">> Done: $user@$host accepts the key in your agent."
else
  [ -e "$key.pub" ] || { echo "No key $key.pub for $host." >&2; exit 1; }
  read -r _ blob _ <"$key.pub"
  echo ">> Revoking $key.pub for $user on $host"
  authorize_key --revoke "$blob" "$user"
  if logs_in true 2>/dev/null; then
    echo "$user@$host still accepts the key; keeping it here." >&2
    exit 1
  fi
  ssh-add -d "$key.pub" 2>/dev/null || true
  rm -f "$key" "$key.pub"
  echo ">> Done: $user@$host refuses the key, and $key is deleted."
fi
