# Rootless Podman maps the user's containers through these two, which must be setuid: the store cannot be.
install -m 4755 "$REPO2REE_ENVIRONMENT_SHADOW"/bin/newuidmap "$REPO2REE_ENVIRONMENT_SHADOW"/bin/newgidmap /usr/local/bin/
echo "researcher:100000:65536" >/etc/subuid
echo "researcher:100000:65536" >/etc/subgid

mkdir -p /etc/containers
cp "$REPO2REE_ENVIRONMENT_FILES"/* /etc/containers/

export XDG_RUNTIME_DIR="/run/user/$uid"
install -d -m 700 -o "$uid" -g "$gid" "$XDG_RUNTIME_DIR"

"${run_as[@]}" podman info >/dev/null

exec "${run_as[@]}" "$@"
