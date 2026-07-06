#!/usr/bin/env bash
# Run the e2e stack: backend + workbench agent + a playwright project, with
# readiness polling and teardown. Invoked by the Makefile e2e targets.
#
#   e2e-stack.sh --project <playwright-project> [--coverage]
#
# With --coverage the backend is started *under* coverage (you can't measure
# an already-running server), the e2e suite runs with E2E_COVERAGE=1 so the
# jsCoverage fixture captures browser V8 coverage, and both processes get a
# graceful SIGTERM at the end so coverage flushes its data on shutdown. Two
# reports come out: backend (test-artifacts/coverage/e2e/) and frontend
# (frontend/test-artifacts/coverage/). Backend data uses its own
# COVERAGE_FILE so it never clobbers be-coverage's, but lives in the same
# test-artifacts/coverage/data dir.
#
# Environment knobs (all optional):
#   E2E_WORKBENCH_IMAGE        bench the backend's catalog offers; empty means
#                              the backend's own catalog default — the pinned
#                              docker:dind digest in api settings — which
#                              every browser tier runs on
#   E2E_WORKBENCH_DOCKER_MODE  dind (default) or host-socket
#   E2E_AGENT_STATE_DIR        agent identity dir (default: test-artifacts/e2e-agent-state)
#   E2E_EXEC_BUNDLE            executor bundle path (default: test-artifacts/exec-bundle)
#   E2E_TOOLS_BUNDLE           tools bundle path (default: test-artifacts/tools-bundle)
#
# The agent always gets the executor/tools bundles: lean env images (the dind
# default, custom benches) need the injection, and images that ship their own
# /nix (the full workbench) skip it — so this is safe for every tier.
set -euo pipefail

usage() {
    echo "usage: $0 --project <playwright-project> [--coverage]" >&2
    exit 2
}

project=
coverage=0
while [ $# -gt 0 ]; do
    case "$1" in
        --project) [ $# -ge 2 ] || usage; project=$2; shift 2 ;;
        --coverage) coverage=1; shift ;;
        *) usage ;;
    esac
done
[ -n "$project" ] || usage

root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"

docker_mode=${E2E_WORKBENCH_DOCKER_MODE:-dind}
state_dir=${E2E_AGENT_STATE_DIR:-$root/test-artifacts/e2e-agent-state}
exec_bundle=${E2E_EXEC_BUNDLE:-$root/test-artifacts/exec-bundle}
tools_bundle=${E2E_TOOLS_BUNDLE:-$root/test-artifacts/tools-bundle}

mkdir -p test-artifacts
if [ "$coverage" -eq 1 ]; then
    coverage_file=$root/test-artifacts/coverage/data/.coverage.e2e
    backend_log=$root/test-artifacts/coverage/e2e/backend.log
    agent_log=$root/test-artifacts/coverage/e2e/agent.log
    mkdir -p test-artifacts/coverage/e2e
    rm -f "$coverage_file" "$coverage_file".* "$agent_log"
    rm -rf frontend/test-artifacts/coverage-raw
else
    backend_log=$root/test-artifacts/api-server.log
    agent_log=$root/test-artifacts/agent.log
    rm -f "$backend_log" "$agent_log"
fi

if [ -n "${E2E_WORKBENCH_IMAGE:-}" ]; then
    export WORKBENCH_IMAGE_CATALOG='[{"id":"pinned","ref":"'"$E2E_WORKBENCH_IMAGE"'","label":"Pinned bench","description":"Bench image pinned for this e2e run."}]'
fi

api_pid=
agent_pid=
stop_stack() {
    if [ -n "$agent_pid" ]; then
        kill -TERM "$agent_pid" 2>/dev/null || true
        wait "$agent_pid" 2>/dev/null || true
    fi
    if [ -n "$api_pid" ]; then
        kill -TERM "$api_pid" 2>/dev/null || true
        wait "$api_pid" 2>/dev/null || true
    fi
}
trap stop_stack EXIT

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

# shellcheck disable=SC2329  # invoked indirectly, via wait_until
agent_connected() {
    curl -sf http://127.0.0.1:8000/api/v1/agents | grep -q '"agents":\[{'
}

echo ">> starting backend on :8000 (log: $backend_log)"
if [ "$coverage" -eq 1 ]; then
    COVERAGE_FILE=$coverage_file coverage run --parallel-mode \
        -m uvicorn repo2ree_api.main:app --host 127.0.0.1 --port 8000 \
        >"$backend_log" 2>&1 &
else
    uvicorn repo2ree_api.main:app --host 127.0.0.1 --port 8000 \
        >"$backend_log" 2>&1 &
fi
api_pid=$!
wait_until "backend" curl -sf http://127.0.0.1:8000/

echo ">> starting workbench agent (log: $agent_log)"
WORKBENCH_API_WS_URL=ws://127.0.0.1:8000/agent/connect \
WORKBENCH_DOCKER_MODE=$docker_mode \
WORKBENCH_AGENT_STATE_DIR=$state_dir \
REPO2REE_EXEC_BUNDLE=$exec_bundle \
REPO2REE_TOOLS_BUNDLE=$tools_bundle \
uv run --package repo2ree-agent python -m repo2ree_agent \
    >"$agent_log" 2>&1 &
agent_pid=$!
wait_until "workbench agent" agent_connected

echo ">> stack ready — running playwright project=$project"
status=0
if [ "$coverage" -eq 1 ]; then
    (cd frontend && E2E_COVERAGE=1 npm exec -- playwright test \
        -c playwright.config.ts --project="$project") || status=$?
else
    (cd frontend && npm exec -- playwright test \
        -c playwright.config.ts --project="$project") || status=$?
fi

echo ">> stopping workbench agent and backend (SIGTERM so coverage can flush)"
stop_stack
trap - EXIT

if [ "$coverage" -eq 1 ]; then
    echo ">> backend coverage"
    COVERAGE_FILE=$coverage_file coverage combine
    COVERAGE_FILE=$coverage_file coverage html -d test-artifacts/coverage/e2e
    COVERAGE_FILE=$coverage_file coverage report
    echo ">> frontend coverage"
    (cd frontend && node scripts/gen-frontend-coverage.mjs)
fi

exit $status
