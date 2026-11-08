mkdir -p /etc/munge /var/lib/munge /var/log/munge /run/munge /var/spool/slurmctld /var/spool/slurmd
dd if=/dev/urandom of=/etc/munge/munge.key bs=1024 count=1 status=none
chmod 400 /etc/munge/munge.key
chmod 755 /run/munge
munged --force

slurmctld
slurmd

for _ in $(seq 60); do
  sinfo --noheader --states=idle 2>/dev/null | grep -q . && break
  sleep 1
done

# A cluster is only one if it runs a job for the user.
"${run_as[@]}" srun --nodes=1 --time=1 hostname || {
  tail -40 /var/log/slurmctld.log /var/log/slurmd.log
  exit 1
}

exec "${run_as[@]}" "$@"
