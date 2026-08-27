#!/usr/bin/env bash
# Remove the Docker state a workbench run leaves behind on this daemon.
#
#   workbench-cleanup.sh                workbench containers + their per-REE volumes
#   workbench-cleanup.sh --store-gc [d] also bundle store volumes unused for d days
#   workbench-cleanup.sh --store        also every bundle store volume
#
# The agent names everything it creates deterministically (docker_runtime.py):
# a `repo2ree-wb-{ree_id}` container, a `repo2ree-ree-{ree_id}` state volume and
# a `repo2ree-dind-{ree_id}` volume for the nested daemon. Those are torn down
# when a REE is deleted, so anything still here belongs to a run that ended
# without deleting its REEs — the normal outcome of a test stack, whose backend
# state goes away with the stack.
#
# Anonymous volumes are swept too. A bench and the scratch containers used to
# probe images run docker:dind, which declares /var/lib/docker and /certs, so
# each one docker creates a hex-named volume nothing can address afterwards.
# Only unreferenced ones go: docker counts stopped containers as users, so a
# dangling anonymous volume belongs to no container at all, running or not.
# Named volumes never match the hex filter, so the store caches below stay out
# of that sweep even though they are dangling whenever no bench is up.
#
# `repo2ree-store-{hash}` volumes are the executor/tools closure every bench
# mounts, keyed by bundle content — ~450MB each, and rebuilding the executor or
# the tools bundle mints a new one and orphans the old, which nothing will ever
# mount again. So they are a cache that needs eviction, not state: --store-gc
# drops the ones no container references and nothing has recreated in <days>
# (default 14), while keeping the bundle this checkout currently resolves to, so
# the next run still starts warm. --store drops all of them, live one included —
# the reclaim-everything hammer, at the cost of one full store copy per bundle
# on the next provision.
#
# Nothing here touches the control-plane or agent-identity volumes — those are
# compose-owned, and `image-stack.sh down --volumes` removes them.
set -euo pipefail

# Anchored on this script's own location, not the cwd: every $root reference
# below names an asset of *this* checkout (dist/bundles, sibling scripts), which
# `git rev-parse` would get wrong when run from inside another repo. Two levels
# up, because the script lives in scripts/test-stack/.
root=$(cd "$(dirname "$0")/../.." && pwd)

store_mode=none
store_max_age_days=14
case "${1:-}" in
    "") ;;
    --store) store_mode=all ;;
    --store-gc) store_mode=gc; [ $# -lt 2 ] || store_max_age_days=$2 ;;
    *) echo "usage: $0 [--store | --store-gc [days]]" >&2; exit 2 ;;
esac

# The store volume this checkout's bundles hash to — protected from --store-gc.
# Resolved through the agent's own loader rather than a copy of its digest
# rule, which would drift. Best effort: unbuilt bundles or no uv just means
# nothing is protected, and at worst one bundle gets copied again.
live_store_volume() {
    local exec_bundle=${REPO2REE_EXEC_BUNDLE:-$root/dist/bundles/exec}
    local tools_bundle=${REPO2REE_TOOLS_BUNDLE:-$root/dist/bundles/tools}
    [ -d "$exec_bundle" ] || return 0
    [ -d "$tools_bundle" ] || tools_bundle=""
    (cd "$root" && uv run --package repo2ree-agent python -c '
import sys
from repo2ree_agent.runtimes.docker.injection import load_injection_bundle
bundle = load_injection_bundle(sys.argv[1], sys.argv[2] or None)
print(bundle.volume_name if bundle else "")
' "$exec_bundle" "$tools_bundle" 2>/dev/null) || true
}

# Store volumes referenced by no container and created over $1 days ago.
# CreatedAt is a creation stamp, not a last-use one — but a store volume is
# only ever created when its content hash first appears, so an old one is one
# whose bundle no build has produced since.
stale_store_volumes() {
    local max_age_days=$1 keep=$2
    docker volume ls -q --filter dangling=true --filter 'name=^repo2ree-store-' 2>/dev/null \
        | { grep -vFx "$keep" || true; } \
        | while read -r name; do
            docker volume inspect "$name" -f '{{.Name}} {{.CreatedAt}}' 2>/dev/null || true
        done \
        | python3 -c '
import datetime as dt, sys
cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=float(sys.argv[1]))
for line in sys.stdin:
    name, _, created = line.partition(" ")
    if dt.datetime.fromisoformat(created.strip()) < cutoff:
        print(name)
' "$max_age_days"
}

containers=$(docker ps -aq --filter 'name=^repo2ree-wb-' 2>/dev/null || true)
if [ -n "$containers" ]; then
    echo ">> removing leftover workbench containers"
    # -v so the container's anonymous volumes go with it; word splitting is the
    # point below: one id per arg.
    # shellcheck disable=SC2086
    docker rm -f -v $containers >/dev/null || true
fi

volume_patterns=(repo2ree-ree- repo2ree-dind-)
[ "$store_mode" = all ] && volume_patterns+=(repo2ree-store-)

volumes=""
for pattern in "${volume_patterns[@]}"; do
    found=$(docker volume ls -q --filter "name=^$pattern" 2>/dev/null || true)
    volumes="$volumes${found:+$found$'\n'}"
done
# Anonymous leftovers: 64 hex chars, referenced by nothing. Filtered after the
# container sweep above, so volumes freed by it are included.
anonymous=$(docker volume ls -q --filter dangling=true 2>/dev/null \
    | grep -E '^[0-9a-f]{64}$' || true)
volumes="$volumes${anonymous:+$anonymous$'\n'}"
volumes=$(echo "$volumes" | grep -v '^$' || true)
if [ -n "$volumes" ]; then
    echo ">> removing leftover workbench volumes"
    # shellcheck disable=SC2086
    docker volume rm $volumes >/dev/null || true
fi

if [ "$store_mode" = gc ]; then
    keep=$(live_store_volume)
    stale=$(stale_store_volumes "$store_max_age_days" "$keep")
    if [ -n "$stale" ]; then
        echo ">> removing bundle store volumes unused for ${store_max_age_days}d${keep:+ (keeping $keep)}"
        # shellcheck disable=SC2086
        docker volume rm $stale >/dev/null || true
    fi
fi
