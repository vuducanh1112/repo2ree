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
# point STACK_IMAGE_REPO/STACK_IMAGE_TAG at a registry — refs that aren't
# local get pulled by docker:
#
#   STACK_IMAGE_REPO=docker.io/vuducanh1112 STACK_IMAGE_TAG=edge \
#     scripts/image-stack.sh up
#
# (or override an individual image with STACK_FRONTEND_IMAGE /
# STACK_BACKEND_IMAGE / STACK_AGENT_IMAGE.)
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

# The agent runs from its own compose file (project name pinned there), so its
# lifecycle stays independent of the control-plane stack.
agent_compose() {
    REPO2REE_AGENT_IMAGE=$agent_image \
        docker compose -f docker-compose.agent.yml "$@"
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

agent_connected() {
    curl -sf "$api_url/api/v1/agents" | grep -q '"agents":\[{'
}

up() {
    resolve_urls
    for img in "$frontend_image" "$backend_image" "$agent_image"; do
        docker image inspect "$img" >/dev/null 2>&1 && continue
        case "$img" in
            */*) ;; # registry ref — docker pulls it on start
            *) echo "$img not found — build the local images first: make images" >&2; exit 1 ;;
        esac
    done

    echo ">> starting compose control plane ($frontend_image, $backend_image)"
    compose_stack up -d

    echo ">> starting workbench agent stack ($agent_image)"
    # Reaching the backend: when the agent shares this daemon with the control
    # plane (the usual case, including nested/DinD CI), host-published ports
    # aren't reliably reachable via the compose file's host.docker.internal
    # default, so join the control-plane network and dial the backend by
    # service name. Only a non-local backend (a remote control plane) falls
    # back to the file's default.
    local control_plane_net
    control_plane_net=$(control_plane_network)
    if [ -n "$control_plane_net" ]; then
        WORKBENCH_API_WS_URL=ws://backend:8000/agent/connect agent_compose up -d >/dev/null
        docker network connect "$control_plane_net" "$agent_container" >/dev/null 2>&1 || true
    else
        agent_compose up -d >/dev/null
    fi

    # The compose network may not have existed before `compose up`, so the
    # service names only resolve from here on — re-check.
    resolve_urls
    wait_until "backend" curl -sf "$api_url/"
    wait_until "workbench agent" agent_connected
    wait_until "frontend" curl -sf "$frontend_url/"
    echo ">> stack up — frontend at $frontend_url"
}

down() {
    echo ">> stopping workbench agent stack"
    agent_compose down >/dev/null 2>&1 || true
    echo ">> stopping compose control plane"
    compose_stack down
}

check() {
    resolve_urls
    curl -sf "$api_url/" >/dev/null \
        || { echo "backend not reachable at $api_url — start the image stack first (make stack-up)" >&2; exit 1; }
    agent_connected \
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
