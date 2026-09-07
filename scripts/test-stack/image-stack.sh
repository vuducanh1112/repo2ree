#!/usr/bin/env bash
# Bring the image-backed demo stack up or down: the compose control plane
# (GUI + backend, :local tags) plus independently managed provider instances.
# The root Compose demo includes one provider, but this harness starts only its
# backend and GUI services so it can still vary provider count and lifecycle.
#
#   image-stack.sh up [options]  start compose + compute locations, wait until ready
#   image-stack.sh down          remove the workbench container and the compose stack
#   image-stack.sh down --volumes  ... and every volume the run created
#   image-stack.sh check         verify backend, connected workbench, and GUI
#   image-stack.sh gui-url  print the GUI base URL for this context
#   image-stack.sh api-url       print the backend base URL for this context
#
# Images default to the :local workbench builds (`up` expects them to exist —
# build with `just images`). To run the same flow against pushed images,
# pass --image-repository/--image-tag — registry refs are
# force-pulled on `up`, so moving tags like :edge always run fresh:
#
#   scripts/test-stack/image-stack.sh up \
#     --image-repository docker.io/vuducanh1112 --image-tag edge
#
# Or override an individual image with --gui-image, --backend-image, or
# --provider-image.
#
# --compute-locations <n> exposes n compute locations by running one provider
# instance per location (default 1) — instance i > 1 gets
# its own compose project, container name, and state volume
# (repo2ree-workbench-<i>), so each keeps a distinct persistent identity.
#
# `up` recreates a leftover repo2ree-workbench container but reuses the pinned
# repo2ree-workbench-state volume, so the workbench id stays stable across runs.
#
# The stack is addressed via its published ports on a normal host. From inside
# a container, localhost is that container rather than the Docker host: use
# service DNS when the caller shares the control-plane network, otherwise use
# the current container's Docker gateway. Use --api-url/--gui-url for a remote
# daemon or another topology.
set -euo pipefail

usage() {
    echo "usage: $0 up [--compute-locations N] [--image-repository REPO] [--image-tag TAG]" >&2
    echo "          [--gui-image REF] [--backend-image REF] [--provider-image REF]" >&2
    echo "          [--api-url URL] [--gui-url URL]" >&2
    echo "       $0 down [--volumes]" >&2
    echo "       $0 check|gui-url|api-url [--api-url URL] [--gui-url URL]" >&2
    exit 2
}

# Anchored on this script's own location, not the cwd: every $root reference
# below names an asset of *this* checkout (dist/bundles, sibling scripts), which
# `git rev-parse` would get wrong when run from inside another repo. Two levels
# up, because the script lives in scripts/test-stack/.
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
caller_attachment_file=$root/test-artifacts/state/image-stack-caller-network

provider_container=repo2ree-provider-docker
compute_location_count=1
image_repository=
image_tag=local
gui_image=${STACK_GUI_IMAGE:-}
backend_image=${STACK_BACKEND_IMAGE:-}
provider_service_image=${STACK_PROVIDER_IMAGE:-}
configured_api_url=
configured_gui_url=

command=${1:-}
[ $# -gt 0 ] && shift
if [ "$command" = up ]; then
    while [ $# -gt 0 ]; do
        case "$1" in
            --compute-locations) [ $# -ge 2 ] || usage; compute_location_count=$2; shift 2 ;;
            --image-repository) [ $# -ge 2 ] || usage; image_repository=$2; shift 2 ;;
            --image-tag) [ $# -ge 2 ] || usage; image_tag=$2; shift 2 ;;
            --gui-image) [ $# -ge 2 ] || usage; gui_image=$2; shift 2 ;;
            --backend-image) [ $# -ge 2 ] || usage; backend_image=$2; shift 2 ;;
            --provider-image) [ $# -ge 2 ] || usage; provider_service_image=$2; shift 2 ;;
            --api-url) [ $# -ge 2 ] || usage; configured_api_url=$2; shift 2 ;;
            --gui-url) [ $# -ge 2 ] || usage; configured_gui_url=$2; shift 2 ;;
            *) usage ;;
        esac
    done
    case "$compute_location_count" in *[!0-9]*|""|0) usage ;; esac
elif [ "$command" = down ]; then
    [ $# -le 1 ] || usage
    [ $# -eq 0 ] || [ "$1" = --volumes ] || usage
elif [ "$command" = check ] || [ "$command" = gui-url ] || [ "$command" = api-url ]; then
    while [ $# -gt 0 ]; do
        case "$1" in
            --api-url) [ $# -ge 2 ] || usage; configured_api_url=$2; shift 2 ;;
            --gui-url) [ $# -ge 2 ] || usage; configured_gui_url=$2; shift 2 ;;
            *) usage ;;
        esac
    done
elif [ $# -ne 0 ]; then
    usage
fi

image_prefix=${image_repository:+${image_repository}/}
gui_image=${gui_image:-${image_prefix}repo2ree-gui:$image_tag}
backend_image=${backend_image:-${image_prefix}repo2ree-backend:$image_tag}
provider_service_image=${provider_service_image:-${image_prefix}repo2ree-provider-docker:$image_tag}

resolve_urls() {
    local default_api_url default_gui_url docker_host
    if getent hosts backend >/dev/null 2>&1 \
            && getent hosts gui >/dev/null 2>&1; then
        default_api_url=http://backend:8000
        default_gui_url=http://gui:3000
    elif [ -f /.dockerenv ]; then
        # Docker Desktop provides this name. Plain Docker Engine does not
        # unless the container was created with host-gateway, so fall back to
        # the gateway of any network attached to the calling container. Host
        # published ports listen there as well as on localhost.
        if getent hosts host.docker.internal >/dev/null 2>&1; then
            docker_host=host.docker.internal
        else
            # single quotes: these are Go-template fields, not shell vars.
            # shellcheck disable=SC2016
            docker_host=$(docker inspect -f \
                '{{range .NetworkSettings.Networks}}{{println .Gateway}}{{end}}' \
                "${HOSTNAME:-}" 2>/dev/null | awk 'NF {print; exit}')
        fi
        if [ -n "$docker_host" ]; then
            default_api_url=http://$docker_host:8000
            default_gui_url=http://$docker_host:3000
        else
            default_api_url=http://localhost:8000
            default_gui_url=http://localhost:3000
        fi
    else
        default_api_url=http://localhost:8000
        default_gui_url=http://localhost:3000
    fi
    api_url=${configured_api_url:-$default_api_url}
    gui_url=${configured_gui_url:-$default_gui_url}
}

compose_stack() {
    REPO2REE_GUI_IMAGE=$gui_image \
    REPO2REE_BACKEND_IMAGE=$backend_image \
        docker compose "$@"
}

# workbench_name <i>: container/project name of the i-th workbench instance. Instance
# 1 keeps the bare historical name so single-workbench flows stay unchanged.
provider_name() {
    local suffix=""
    [ "$1" -gt 1 ] && suffix="-$1"
    echo "$provider_container$suffix"
}

# The workbenches run from their own compose file, so their lifecycle stays
# independent of the control-plane stack. Each instance is its own compose
# project (-p) with its own container name and state volume.
provider_compose() {
    local name=$1
    shift
    REPO2REE_PROVIDER_IMAGE=$provider_service_image \
    REPO2REE_PROVIDER_CONTAINER=$name \
    REPO2REE_PROVIDER_STATE_VOLUME=$name-state \
        docker compose -p "$name" -f docker-compose.workbench.yml "$@"
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

# Attach the calling devcontainer to the local control-plane network. Merely
# sharing its Docker socket does not put it in the same network namespace, and
# a published port on the Docker host is not guaranteed to hairpin through
# host.docker.internal. Record only attachments made here so down() never
# disconnects a network the user attached themselves.
attach_caller_to_control_plane() {
    [ -f /.dockerenv ] || return 0
    [ -n "${HOSTNAME:-}" ] || return 0
    docker inspect "$HOSTNAME" >/dev/null 2>&1 || return 0

    local network networks
    network=$(control_plane_network)
    [ -n "$network" ] || return 0
    # single quotes: this is a Go-template field, not a shell variable.
    # shellcheck disable=SC2016
    networks=$(docker inspect -f '{{json .NetworkSettings.Networks}}' "$HOSTNAME")
    if printf '%s\n' "$networks" | grep -Fq "\"$network\""; then
        return 0
    fi

    docker network connect "$network" "$HOSTNAME"
    mkdir -p "$(dirname "$caller_attachment_file")"
    printf '%s %s\n' "$HOSTNAME" "$network" >"$caller_attachment_file"
    # stderr keeps gui-url/api-url stdout machine-readable when either command
    # performs the first attachment.
    echo ">> attached calling container to $network" >&2
}

detach_owned_caller_network() {
    [ -f "$caller_attachment_file" ] || return 0
    local container network
    read -r container network <"$caller_attachment_file" || true
    if [ -n "${container:-}" ] && [ -n "${network:-}" ]; then
        docker network disconnect "$network" "$container" >/dev/null 2>&1 || true
    fi
    rm -f "$caller_attachment_file"
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
    echo "failed probe: $*" >&2
    "$@" >&2 || true
    return 1
}

providers_connected() {
    local want=$1
    # Parse the JSON structurally rather than grepping a field name, so the
    # probe cannot silently drift from the wire format.
    local count
    count=$(curl -fsS --connect-timeout 1 --max-time 1 \
        "$api_url/api/v1/providers" \
        | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("providers", [])))' \
        2>/dev/null) || count=0
    [ "${count:-0}" -ge "$want" ]
}

up() {
    resolve_urls
    for img in "$gui_image" "$backend_image" "$provider_service_image"; do
        case "$img" in
            # Registry ref: always pull. Compose alone would reuse a stale
            # local copy of a moving tag like :edge (its default pull policy
            # is "missing"), so the run wouldn't test what the registry holds.
            */*) echo ">> pulling $img"; docker pull "$img" ;;
            *) docker image inspect "$img" >/dev/null 2>&1 \
                || { echo "$img not found — build the local images first: just images" >&2; exit 1; } ;;
        esac
    done

    echo ">> starting compose control plane ($gui_image, $backend_image)"
    compose_stack up -d backend gui

    echo ">> starting $compute_location_count Docker provider service(s) ($provider_service_image)"
    # Reaching the backend: both the provider and every child workbench join the
    # control-plane network and dial by service name. Joining only the provider
    # is insufficient: its child containers otherwise cannot resolve `backend`.
    # Only a non-local backend (a remote control plane) falls back to the
    # standalone provider Compose file's host-gateway defaults.
    local control_plane_net i name
    control_plane_net=$(control_plane_network)
    for i in $(seq 1 "$compute_location_count"); do
        name=$(provider_name "$i")
        if [ -n "$control_plane_net" ]; then
            PROVIDER_API_WS_URL=ws://backend:8000/provider/connect \
            PROVIDER_WORKBENCH_API_WS_URL=ws://backend:8000/workbench/connect \
            PROVIDER_WORKBENCH_DOCKER_NETWORK="$control_plane_net" \
                provider_compose "$name" up -d >/dev/null
            docker network connect "$control_plane_net" "$name" >/dev/null 2>&1 || true
        else
            provider_compose "$name" up -d >/dev/null
        fi
    done

    # The compose network may not have existed before `compose up`, so the
    # service names only resolve from here on. A devcontainer on the same
    # daemon joins it before resolving the endpoints.
    attach_caller_to_control_plane
    resolve_urls
    echo ">> probing stack endpoints — API $api_url, GUI $gui_url"
    wait_until "backend at $api_url" curl -fsS --connect-timeout 1 --max-time 1 "$api_url/"
    wait_until "$compute_location_count provider service(s)" providers_connected "$compute_location_count"
    wait_until "gui at $gui_url" curl -fsS --connect-timeout 1 --max-time 1 "$gui_url/"
    echo ">> stack up — GUI at $gui_url"
}

# down [--volumes]: stop the stack. With --volumes, also drop every volume the
# run created — the compose ones (backend data, workbench identity) and whatever
# workbench state the workbench left on the daemon. That is the right default for a
# test stack, where a surviving backend volume outlives the REEs it describes;
# the plain `down` keeps the volumes so a demo stack resumes where it left off.
down() {
    local with_volumes=${1:-}
    local down_args=()
    [ "$with_volumes" = "--volumes" ] && down_args=(-v)

    # The control-plane network cannot be removed while the calling
    # devcontainer remains attached to it.
    detach_owned_caller_network

    # Tear down every workbench instance found on the daemon, not just
    # the requested number — a previous `up` may have started more.
    echo ">> stopping workbench service stack(s)"
    local name
    for name in $(docker ps -a --format '{{.Names}}' \
        | grep -E "^${provider_container}(-[0-9]+)?$" || true); do
        provider_compose "$name" down "${down_args[@]}" >/dev/null 2>&1 || true
    done
    echo ">> stopping compose control plane"
    compose_stack down "${down_args[@]}"

    [ "$with_volumes" = "--volumes" ] && "$root/scripts/test-stack/workbench-cleanup.sh"
    return 0
}

check() {
    attach_caller_to_control_plane
    resolve_urls
    curl -fsS --connect-timeout 1 --max-time 1 "$api_url/" >/dev/null \
        || { echo "backend not reachable at $api_url — start the image stack first (just stack-up)" >&2; exit 1; }
    providers_connected 1 \
        || { echo "no provider service connected — start the provider container (just stack-up)" >&2; exit 1; }
    curl -fsS --connect-timeout 1 --max-time 1 "$gui_url/" >/dev/null \
        || { echo "GUI not reachable at $gui_url — start the image stack first (just stack-up)" >&2; exit 1; }
}

case "$command" in
    up) up ;;
    down) down "${1:-}" ;;
    check) check ;;
    gui-url) attach_caller_to_control_plane; resolve_urls; echo "$gui_url" ;;
    api-url) attach_caller_to_control_plane; resolve_urls; echo "$api_url" ;;
    *) usage ;;
esac
