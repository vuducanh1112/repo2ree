# A daemon nested in a container needs the cgroup it starts in to delegate its controllers.
if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
  mkdir -p /sys/fs/cgroup/init
  xargs -rn1 </sys/fs/cgroup/cgroup.procs >/sys/fs/cgroup/init/cgroup.procs 2>/dev/null || true
  sed -e 's/ / +/g' -e 's/^/+/' </sys/fs/cgroup/cgroup.controllers >/sys/fs/cgroup/cgroup.subtree_control
fi

dockerd --group "$gid" >/var/log/dockerd.log 2>&1 &

for _ in $(seq 60); do
  "${run_as[@]}" docker info >/dev/null 2>&1 && break
  sleep 1
done
"${run_as[@]}" docker info >/dev/null || {
  tail -40 /var/log/dockerd.log
  exit 1
}

exec "${run_as[@]}" "$@"
