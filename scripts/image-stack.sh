#!/usr/bin/env bash
# Bring the image-backed demo stack up or down: the compose control plane
# (frontend + backend, :local tags) plus the workbench agent, which the
# control-plane compose deliberately doesn't manage — it runs from its own
# docker-compose.agent.yml (see docker-compose.yml).
#
#   image-stack.sh up            start compose + agent, wait until ready
#   image-stack.sh down          remove the agent container and the compose stack
#   image-stack.sh check         verify backend, connected agent, and frontend
#   image-stack.sh frontend-url  print the frontend base URL for this context
#
# Images default to the :local workbench builds (`up` expects them to exist —
# build with `make images`). To run the same flow against pushed images,
# point STACK_IMAGE_REPO/STACK_IMAGE_TAG at a registry — registry refs are
# force-pulled on `up`, so moving tags like :edge always run fresh:
#
#   STACK_IMAGE_REPO=docker.io/vuducanh1112 STACK_IMAGE_TAG=edge \
#     scripts/image-stack.sh up
#
# (or override an individual image with STACK_FRONTEND_IMAGE /
# STACK_BACKEND_IMAGE / STACK_AGENT_IMAGE.)
#
# STACK_AGENTS=<n> runs n agent instances (default 1) — instance i > 1 gets
# its own compose project, container name, and state volume
# (repo2ree-agent-<i>), so each keeps a distinct persistent identity.
#
# `up` recreates a leftover repo2ree-agent container but reuses the pinned
# repo2ree-agent-state volume, so the agent id stays stable across runs.
#
# The stack is addressed via the host-published ports (localhost:8000/:3000).
# From inside a container on the compose network (the devcontainer), those
# ports aren't on localhost, so when the compose service name `backend`
# resolves, the service DNS names are used instead. Override with
# STACK_API_URL / STACK_FRONTEND_URL if neither fits.
set -euo pipefail

usage() {
    echo "usage: $0 up|down|check|frontend-url" >&2
    exit 2
}

root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"

agent_container=repo2ree-agent
# Agent instances to run (default 1). Instance i > 1 becomes its own compose
# project repo2ree-agent-<i> with its own state volume, so each keeps a
# distinct persistent identity — the multi-agent e2e specs need >= 2, and a
# stress run can push it higher.
stack_agents=${STACK_AGENTS:-1}

image_prefix=${STACK_IMAGE_REPO:+${STACK_IMAGE_REPO}/}
image_tag=${STACK_IMAGE_TAG:-local}
frontend_image=${STACK_FRONTEND_IMAGE:-${image_prefix}repo2ree-frontend:$image_tag}
backend_image=${STACK_BACKEND_IMAGE:-${image_prefix}repo2ree-backend:$image_tag}
agent_image=${STACK_AGENT_IMAGE:-${image_prefix}repo2ree-agent:$image_tag}

resolve_urls() {
    if getent hosts backend >/dev/null 2>&1; then
        api_url=${STACK_API_URL:-http://backend:8000}
        frontend_url=${STACK_FRONTEND_URL:-http://frontend:3000}
    else
        api_url=${STACK_API_URL:-http://localhost:8000}
        frontend_url=${STACK_FRONTEND_URL:-http://localhost:3000}
    fi
}

compose_stack() {
    REPO2REE_FRONTEND_IMAGE=$frontend_image \
    REPO2REE_BACKEND_IMAGE=$backend_image \
        docker compose "$@"
}

# agent_name <i>: container/project name of the i-th agent instance. Instance
# 1 keeps the bare historical name so single-agent flows stay unchanged.
agent_name() {
    local suffix=""
    [ "$1" -gt 1 ] && suffix="-$1"
    echo "$agent_container$suffix"
}

# The agents run from their own compose file, so their lifecycle stays
# independent of the control-plane stack. Each instance is its own compose
# project (-p) with its own container name and state volume.
agent_compose() {
    local name=$1
    shift
    REPO2REE_AGENT_IMAGE=$agent_image \
    REPO2REE_AGENT_CONTAINER=$name \
    REPO2REE_AGENT_STATE_VOLUME=$name-state \
        docker compose -p "$name" -f docker-compose.agent.yml "$@"
}

# The docker network the control-plane backend is attached to, or empty when
# the backend isn't a local compose service on this daemon.
control_plane_network() {
    # single quotes: the $k/$_ below are Go-template fields, not shell vars.
    # shellcheck disable=SC2016
    compose_stack ps -q backend 2>/dev/null | head -n1 \
        | xargs -r docker inspect -f '{{range $k,$_ := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null \
        | awk '{print $1}'
}

# wait_until <description> <command...>: poll for up to 30s.
wait_until() {
    local what=$1
    shift
    for i in $(seq 1 30); do
        if "$@" >/dev/null 2>&1; then return 0; fi
        echo "  waiting for $what... ($i/30)"
        sleep 1
    done
    echo "$what did not become ready" >&2
    return 1
}

agents_connected() {
    local want=$1
    [ "$(curl -sf "$api_url/api/v1/agents" | grep -o '"agentId"' | wc -l)" -ge "$want" ]
}

up() {
    resolve_urls
    for img in "$frontend_image" "$backend_image" "$agent_image"; do
        case "$img" in
            # Registry ref: always pull. Compose alone would reuse a stale
            # local copy of a moving tag like :edge (its default pull policy
            # is "missing"), so the run wouldn't test what the registry holds.
            */*) echo ">> pulling $img"; docker pull "$img" ;;
            *) docker image inspect "$img" >/dev/null 2>&1 \
                || { echo "$img not found — build the local images first: make images" >&2; exit 1; } ;;
        esac
    done

    echo ">> starting compose control plane ($frontend_image, $backend_image)"
    compose_stack up -d

    echo ">> starting $stack_agents workbench agent(s) ($agent_image)"
    # Reaching the backend: when the agent shares this daemon with the control
    # plane (the usual case, including nested/DinD CI), host-published ports
    # aren't reliably reachable via the compose file's host.docker.internal
    # default, so join the control-plane network and dial the backend by
    # service name. Only a non-local backend (a remote control plane) falls
    # back to the file's default.
    local control_plane_net i name
    control_plane_net=$(control_plane_network)
    for i in $(seq 1 "$stack_agents"); do
        name=$(agent_name "$i")
        if [ -n "$control_plane_net" ]; then
            WORKBENCH_API_WS_URL=ws://backend:8000/agent/connect \
                agent_compose "$name" up -d >/dev/null
            docker network connect "$control_plane_net" "$name" >/dev/null 2>&1 || true
        else
            agent_compose "$name" up -d >/dev/null
        fi
    done

    # The compose network may not have existed before `compose up`, so the
    # service names only resolve from here on — re-check.
    resolve_urls
    wait_until "backend" curl -sf "$api_url/"
    wait_until "$stack_agents workbench agent(s)" agents_connected "$stack_agents"
    wait_until "frontend" curl -sf "$frontend_url/"
    echo ">> stack up — frontend at $frontend_url"
}

down() {
    # Tear down every agent instance found on the daemon, not just
    # $stack_agents of them — a previous `up` may have started more.
    echo ">> stopping workbench agent stack(s)"
    local name
    for name in $(docker ps -a --format '{{.Names}}' \
        | grep -E "^${agent_container}(-[0-9]+)?$" || true); do
        agent_compose "$name" down >/dev/null 2>&1 || true
    done
    echo ">> stopping compose control plane"
    compose_stack down
}

check() {
    resolve_urls
    curl -sf "$api_url/" >/dev/null \
        || { echo "backend not reachable at $api_url — start the image stack first (make stack-up)" >&2; exit 1; }
    agents_connected 1 \
        || { echo "no workbench agent connected — start the agent container (make stack-up)" >&2; exit 1; }
    curl -sf "$frontend_url/" >/dev/null \
        || { echo "frontend not reachable at $frontend_url — start the image stack first (make stack-up)" >&2; exit 1; }
}

case "${1:-}" in
    up) up ;;
    down) down ;;
    check) check ;;
    frontend-url) resolve_urls; echo "$frontend_url" ;;
    *) usage ;;
esac
