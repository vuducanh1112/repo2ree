#!/usr/bin/env bash
# Give a VM a dedicated e2e user that your SSH agent can log in as, or take it away again.
#
#   tools/ssh/setup-vm.sh [--confirm] [--name machine] <admin login> [vm user]
#   tools/ssh/setup-vm.sh --revoke [--name machine] <admin login> [vm user]
#
# <admin login> is how you reach the VM today with root or sudo rights, such as
# ubuntu@203.0.113.7 or an alias from ~/.ssh/config. Setting up
#   1. makes the key ~/.ssh/repo2ree-<host>, unless it exists (set a passphrase),
#   2. loads it into your agent (--confirm: the agent asks you before each use),
#   3. copies authorize-key.sh to a temporary directory on the VM and runs it as
#      root, which creates the vm user (default repo2ree) and authorizes the key,
#   4. logs in as that user with the key, to prove it works,
#   5. copies the VM's host keys, as the known_hosts files your logins just
#      checked have them, into this checkout's .config/known_hosts, replacing
#      any it had for the VM, and
#   6. names the VM in .config/machines.toml as the e2e machine `vm` (--name
#      picks another name), as host = "<vm user>@<address>". A name already
#      there is left as it is, whichever VM it names.
# Steps 5 and 6 name the VM by its address: an alias from ~/.ssh/config is
# resolved, since the dev container does not have your aliases. A VM on a port
# other than 22 gets its host keys but no machines entry, which cannot hold a
# port: name it there through an ssh alias of the dev container's own.
#
# E2e runs in the dev container check host keys against .config/known_hosts and
# their own ~/.ssh/known_hosts, and refuse a host neither knows rather than ask
# halfway through a run. .config is in the checkout, so both files outlive a
# rebuilt dev container; Git ignores them.
#
# Revoking removes the key from the VM, checks it no longer logs in, then drops
# it from your agent and deletes it here. It also removes the VM's host keys
# from .config/known_hosts and its entry from .config/machines.toml, if that
# entry names this VM. Setting up again makes a new key.
#
# Run it on your own computer, not in the dev container: the private key stays
# here, and the container uses it through the agent that VS Code forwards.
#
# Examples:
#   tools/ssh/setup-vm.sh ubuntu@203.0.113.7             user repo2ree, via your admin login
#   tools/ssh/setup-vm.sh my-vm                          the same, via a ~/.ssh/config alias
#   tools/ssh/setup-vm.sh ubuntu@203.0.113.7 e2e         a user named e2e
#   tools/ssh/setup-vm.sh --confirm ubuntu@203.0.113.7   needs 1Password or Secretive on macOS
#   tools/ssh/setup-vm.sh --name big ubuntu@203.0.113.7  the e2e machine `big`
#   tools/ssh/setup-vm.sh --revoke ubuntu@203.0.113.7
#   tools/ssh/setup-vm.sh --revoke ubuntu@203.0.113.7 e2e
# Revoke with the admin login you set up with: the key is named after its host
# part, so ubuntu@203.0.113.7 and my-vm are different VMs here.
set -euo pipefail

action=setup add=(ssh-add) name=vm
while [ $# -gt 0 ]; do
  case "$1" in
    --confirm) add=(ssh-add -c); shift ;;
    --revoke) action=revoke; shift ;;
    --name) name=${2:?--name needs a machine name}; shift 2 ;;
    *) break ;;
  esac
done
[ $# -ge 1 ] || { sed -n '4,5s/^# //p' "$0"; exit 2; }
admin=$1 user=${2:-repo2ree}
host=${admin#*@}
key=~/.ssh/repo2ree-${host//[^A-Za-z0-9.-]/_}
here=$(cd "$(dirname "$0")" && pwd)
config=$(cd "$here/../.." && pwd)/.config

# Where an alias from ~/.ssh/config leads: the dev container has no such alias, so
# the machines file and the known hosts name the VM by its address.
read -r address port < <(ssh -G "$host" 2>/dev/null | awk '/^hostname /{h=$2} /^port /{p=$2} END{print h, p}')
entry=$address
[ "$port" = 22 ] || entry="[$address]:$port"

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

# Copy the VM's host keys from the known_hosts files ssh uses here, which the
# logins above just checked, into the checkout's, replacing any it had.
share_host_key() {
  local file found=""
  mkdir -p "$config"
  for file in $(ssh -G "$host" 2>/dev/null | awk '/^userknownhostsfile /{$1=""; print}'); do
    file=${file/#\~/$HOME}
    if [ -f "$file" ]; then found+=$(ssh-keygen -F "$entry" -f "$file" | grep -v '^#' || true)$'\n'; fi
  done
  found=$(printf '%s' "$found" | sed '/^$/d' | sort -u)
  [ -n "$found" ] || { echo "No host key for $entry in your known_hosts; log in to it once and run this again." >&2; exit 1; }
  forget_host_key
  printf '%s\n' "$found" >>"$config/known_hosts"
}

forget_host_key() {
  [ -f "$config/known_hosts" ] || return 0
  ssh-keygen -R "$entry" -f "$config/known_hosts" >/dev/null 2>&1 || true
  rm -f "$config/known_hosts.old"
}

# Name the VM as an e2e machine, unless the name is taken (by it or another).
add_machine() {
  local machines=$config/machines.toml
  if grep -qsxF "[machines.$name]" "$machines"; then
    echo ">> .config/machines.toml already names a machine $name; left as it is"
  elif [ "$port" != 22 ]; then
    echo ">> $address listens on port $port: name it in .config/machines.toml through an ssh alias yourself"
  else
    [ ! -s "$machines" ] || printf '\n' >>"$machines"
    printf '[machines.%s]\nhost = "%s@%s"\n' "$name" "$user" "$address" >>"$machines"
    echo ">> .config/machines.toml now names $user@$address as the e2e machine $name"
  fi
}

# Take the machine out of the machines file, if it is this VM.
remove_machine() {
  local machines=$config/machines.toml
  [ -f "$machines" ] || return 0
  awk -v header="[machines.$name]" -v host="host = \"$user@$address\"" '
    function flush() { if (!(block[1] == header && mine)) for (i = 1; i <= n; i++) print block[i]; n = 0; mine = 0 }
    /^\[/ { flush() }
    { block[++n] = $0; if ($0 == host) mine = 1 }
    END { flush() }
  ' "$machines" >"$machines.new" && mv "$machines.new" "$machines"
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
  share_host_key
  add_machine
  echo ">> Done: $user@$host accepts the key in your agent. Next, in the dev container: just prepare-e2e-machine $name"
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
  forget_host_key
  remove_machine
  echo ">> Done: $user@$host refuses the key, $key is deleted, and .config no longer names it."
fi
