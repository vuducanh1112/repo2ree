#!/usr/bin/env bash
# Run the e2e stack: backend + workbench agent(s) + a playwright project,
# with readiness polling and teardown. Invoked by the Makefile e2e targets.
# `--agents <n>` sets how many agents connect (default 1). Specs that need
# more than the stack offers (e.g. the multi-agent spec, which needs 2) skip
# themselves, so any project runs against any agent count.
#
#   e2e-stack.sh --project <playwright-project> [--agents <n>]
#   e2e-stack.sh --script <path> --tier <name> [--agents <n>] [--record <cast>]
#
# The --script mode runs an arbitrary client against the same live stack instead
# of a playwright project — used by the pure-API agent walkthrough. With
# --record the run is captured via asciinema into a .cast terminal recording.
#
# Every run is measured; there is no flag to turn it off. The backend *and* every
# agent start under coverage (you cannot measure an already-running process), and
# every process gets a graceful SIGTERM at the end so coverage flushes on
# shutdown. One report comes out: test-artifacts/coverage/python/<tier>/.
#
# The *browser* is not measured, deliberately. These runs used to capture V8
# coverage per test and merge it with monocart, but Vite's dev sourcemaps identify
# sources by basename alone, so 18 same-named files collapsed into shared entries
# and the report was wrong without saying so. UI coverage belongs to component
# tests in the `node` tier, where Vitest transforms the files itself and knows
# their real paths. An e2e run proves the pipeline works; it is a poor instrument
# for "does this component have a test".
#
# The tier IS the playwright project — there is no separate --coverage <tier> to
# disagree with it. That flag used to exist, and nothing checked the two against
# each other: `--project demo --coverage e2e` ran the demo suite and wrote the e2e
# tier's data, silently mislabelling the report. --script has no project, so it
# names its tier explicitly.
#
# The tier selects its own data directory under
# test-artifacts/coverage/python/data/<tier>/, so it never blends with the pytest
# tiers or with another stack tier. `make be-coverage-combined` unions them. See
# the tier map in mk/be-tests.mk.
#
# Debugging without instrumentation: bring up a stack yourself (`make stack-up`)
# and use the `-on-stack` targets, or point playwright at a single spec. Those
# paths are unmeasured because the processes are in containers, which is also
# what keeps an un-instrumented topology on the push gate.
#
# The agents are measured, not just the backend: an e2e run is the heaviest
# exercise the agent package gets (docker runtime, control link, injection,
# chunked transfers), and leaving them out reported that work as uncovered.
# Server and agents therefore share one COVERAGE_FILE under --parallel-mode,
# each writing its own suffixed data file, combined at the end.
#
# Environment knobs (all optional):
#   E2E_WORKBENCH_IMAGE        bench the backend's catalog offers; empty means
#                              the backend's own catalog default — the pinned
#                              docker:dind digest in api settings — which
#                              every browser tier runs on
#   E2E_WORKBENCH_DOCKER_MODE  dind (default) or host-socket
#   E2E_AGENT_STATE_DIR        agent identity dir (default: test-artifacts/state/agents);
#                              with --agents N, agent i > 1 uses <dir>-<i> so
#                              each keeps a distinct persistent identity
#   E2E_EXEC_BUNDLE            executor bundle path (default: dist/bundles/exec)
#   E2E_TOOLS_BUNDLE           tools bundle path (default: dist/bundles/tools)
#
# The agent always gets the executor/tools bundles: lean env images (the dind
# default, custom benches) need the injection, and images that ship their own
# /nix (the full workbench) skip it — so this is safe for every tier.
set -euo pipefail

usage() {
    echo "usage: $0 (--project <playwright-project> | --script <path> --tier <name>)" \
        "[--agents <n>] [--record <cast>]" >&2
    exit 2
}

# The stack can drive either a playwright project (browser e2e/demo) or an
# arbitrary --script against the same live backend+agent — that second mode is
# how the pure-API agent walkthrough runs. --record wraps a --script run in
# asciinema so the terminal session becomes a .cast artifact.
project=
script=
record=
agents=1
tier=
while [ $# -gt 0 ]; do
    case "$1" in
        --project) [ $# -ge 2 ] || usage; project=$2; shift 2 ;;
        --script) [ $# -ge 2 ] || usage; script=$2; shift 2 ;;
        --tier) [ $# -ge 2 ] || usage; tier=$2; shift 2 ;;
        --record) [ $# -ge 2 ] || usage; record=$2; shift 2 ;;
        --agents) [ $# -ge 2 ] || usage; agents=$2; shift 2 ;;
        *) usage ;;
    esac
done
# Exactly one runner: a playwright project or a script.
if { [ -n "$project" ] && [ -n "$script" ]; } || { [ -z "$project" ] && [ -z "$script" ]; }; then usage; fi
[ -z "$record" ] || [ -n "$script" ] || usage  # --record only applies to --script
[ "$agents" -ge 1 ] 2>/dev/null || usage
# The tier is the project — one name, so the report can never be labelled with a
# suite that did not produce it. --script has no project and must say which tier
# its run belongs to; --tier alongside --project would be a second name for the
# same thing, so it is rejected rather than silently preferred.
if [ -n "$project" ]; then
    [ -z "$tier" ] || { echo "--tier is implied by --project ($project); drop it" >&2; exit 2; }
    tier=$project
fi
[ -n "$tier" ] || { echo "--script needs --tier <name> to say which tier it measures" >&2; exit 2; }

# Anchored on this script's own location, not the cwd: every $root reference
# below names an asset of *this* checkout (dist/bundles, sibling scripts), which
# `git rev-parse` would get wrong when run from inside another repo. Two levels
# up, because the script lives in scripts/test-stack/.
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"

# Check the project resolves *before* building anything. Playwright is the only
# thing that knows which projects exist, and it is not consulted until the very
# end of a run — so a name it rejects used to cost a full backend + agent
# startup first, and then failed with the stack already up. `--list` answers in
# well under a second. Playwright's own message is passed through because it
# enumerates the available projects, which is exactly what you need to see.
if [ -n "$project" ]; then
    if ! probe=$(cd gui && npm exec -- playwright test -c playwright.config.ts \
            --project="$project" --list 2>&1); then
        printf '%s\n' "$probe" >&2
        echo "refusing to start the stack: playwright rejected --project=$project" >&2
        exit 2
    fi
fi

docker_mode=${E2E_WORKBENCH_DOCKER_MODE:-dind}
state_dir=${E2E_AGENT_STATE_DIR:-$root/test-artifacts/state/agents}
exec_bundle=${E2E_EXEC_BUNDLE:-$root/dist/bundles/exec}
tools_bundle=${E2E_TOOLS_BUNDLE:-$root/dist/bundles/tools}

# agent_log <i>: log path for the i-th agent (agent-<tier>.log, agent-<tier>-2.log,
# ...). Every log shares one logs/ directory, so without the tier a demo run would
# clobber an e2e run's agent log.
agent_log() {
    local suffix=""
    [ "$1" -gt 1 ] && suffix="-$1"
    echo "$agent_log_dir/agent-$tier$suffix.log"
}

# Logs live under test-artifacts/logs/, not inside a coverage report directory:
# a directory `coverage html` owns should hold only the report it generates.
log_dir=$root/test-artifacts/logs
agent_log_dir=$log_dir
coverage_data_dir=$root/test-artifacts/coverage/python/data/$tier
coverage_file=$coverage_data_dir/.coverage
backend_log=$log_dir/backend-$tier.log
run_token="e2e-$tier-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
port_file=$(mktemp)
api_base_url=
control_state_dir=${E2E_CONTROL_STATE_DIR:-$root/test-artifacts/state/control/$run_token}
mkdir -p "$log_dir" "$state_dir" "$coverage_data_dir" "$control_state_dir"
# Start the tier's data fresh: --parallel-mode leaves one suffixed file per
# process, so a previous run's files would otherwise be combined in as well
# and report a union of two runs as one.
rm -f "$coverage_file" "$coverage_file".*
for i in $(seq 1 "$agents"); do rm -f "$(agent_log "$i")"; done

if [ -n "${E2E_WORKBENCH_IMAGE:-}" ]; then
    export WORKBENCH_IMAGE_CATALOG='[{"id":"pinned","ref":"'"$E2E_WORKBENCH_IMAGE"'","label":"Pinned bench","description":"Bench image pinned for this e2e run."}]'
fi

api_pid=
agent_pids=()
client_pid=
stop_stack() {
    local pid
    if [ -n "$client_pid" ]; then
        kill -TERM "$client_pid" 2>/dev/null || true
        wait "$client_pid" 2>/dev/null || true
        client_pid=
    fi
    for pid in "${agent_pids[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
    if [ -n "$api_pid" ]; then
        kill -TERM "$api_pid" 2>/dev/null || true
        wait "$api_pid" 2>/dev/null || true
    fi
    # The backend state this stack ran on is throwaway, so workbenches the specs
    # did not delete are unreachable. The agent labels every per-run resource;
    # select that label so parallel stacks and developers' benches survive.
    "$root/scripts/test-stack/workbench-cleanup.sh" --owner "$run_token"
    rm -f "$port_file"
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
agents_connected() {
    local want=$1
    # Parse the JSON structurally rather than grepping a field name, so the
    # probe cannot silently drift from the wire format.
    local count
    count=$(curl -sf "$api_base_url/api/v1/agents" \
        | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("agents", [])))' \
        2>/dev/null) || count=0
    [ "${count:-0}" -ge "$want" ]
}

# The launcher binds port 0 before publishing its number, so no other process
# can take the chosen port between discovery and Uvicorn startup. Readiness also
# checks the child PID: an unrelated healthy API can never satisfy this probe.
wait_for_backend() {
    local port
    for i in $(seq 1 30); do
        if ! kill -0 "$api_pid" 2>/dev/null; then
            echo "backend process exited before readiness" >&2
            tail -n 50 "$backend_log" >&2 || true
            return 1
        fi
        if [ -s "$port_file" ]; then
            port=$(cat "$port_file")
            case "$port" in
                *[!0-9]*|"") ;;
                *)
                    api_base_url="http://127.0.0.1:$port"
                    if curl -sf "$api_base_url/" >/dev/null 2>&1; then return 0; fi
                    ;;
            esac
        fi
        echo "  waiting for owned backend... ($i/30)"
        sleep 1
    done
    echo "owned backend did not become ready" >&2
    return 1
}

echo ">> starting backend on an isolated port under coverage (log: $backend_log)"
UPLOAD_STAGING_DIR=$control_state_dir/upload-staging \
WORKBENCH_REGISTRY_FILE=$control_state_dir/workbench-registry.json \
REE_INDEX_FILE=$control_state_dir/ree-index.json \
RUN_REGISTRY_DIR=$control_state_dir/runs \
COVERAGE_FILE=$coverage_file coverage run --parallel-mode \
    "$root/scripts/test-stack/serve-e2e-api.py" "$port_file" \
    >"$backend_log" 2>&1 &
api_pid=$!
wait_for_backend
echo ">> backend ready at $api_base_url (pid $api_pid)"

# start_agent <state-dir> <log>: one workbench agent process, backgrounded.
# It runs through `coverage run --parallel-mode` sharing the tier's COVERAGE_FILE
# with the backend, so each process writes its own suffixed data file and the
# combine at the end picks all of them up. `sigterm = true` (pyproject.toml) is
# what makes the flush happen when stop_stack signals them.
start_agent() {
    WORKBENCH_API_WS_URL="${api_base_url/http:/ws:}/agent/connect" \
    WORKBENCH_DOCKER_MODE=$docker_mode \
    WORKBENCH_AGENT_STATE_DIR=$1 \
    REPO2REE_EXEC_BUNDLE=$exec_bundle \
    REPO2REE_TOOLS_BUNDLE=$tools_bundle \
    REPO2REE_RESOURCE_OWNER=$run_token \
    COVERAGE_FILE=$coverage_file \
    uv run --package repo2ree-agent coverage run --parallel-mode \
        -m repo2ree_agent >"$2" 2>&1 &
    agent_pids+=($!)
}

for i in $(seq 1 "$agents"); do
    dir=$state_dir
    [ "$i" -gt 1 ] && dir="${state_dir}-$i"
    echo ">> starting workbench agent $i/$agents (log: $(agent_log "$i"))"
    start_agent "$dir" "$(agent_log "$i")"
done
wait_until "$agents workbench agent(s)" agents_connected "$agents"

# Start the client as a separately waitable process. `wait -n` below watches it
# alongside the exact backend and agent PIDs; infrastructure death aborts the
# client immediately instead of degrading into a late browser timeout.
if [ -n "$script" ]; then
    echo ">> stack ready — running script=$script"
    # The script drives the live backend over HTTP; hand it the base URL the
    # stack just brought up. --record wraps the run in asciinema so the terminal
    # session is captured as a .cast, the pure-API counterpart of a demo video.
    if [ -n "$record" ]; then
        mkdir -p "$(dirname "$record")"
        # asciinema does NOT propagate the recorded command's exit code — it
        # returns 0 even when the command fails. So the walkthrough writes its
        # real status to a sentinel file that we read back; otherwise a failing
        # run would record cleanly and still report success, defeating the CI
        # check. Env exported before asciinema is inherited by the command.
        rc_file=$(mktemp)
        (
            API_BASE_URL=$api_base_url \
                asciinema rec --overwrite -c "'$script'; echo \$? > '$rc_file'" "$record" || true
            recorded_status=$(cat "$rc_file" 2>/dev/null || echo 1)
            rm -f "$rc_file"
            echo ">> recorded terminal session: $record (walkthrough exit $recorded_status)"
            exit "$recorded_status"
        ) &
        client_pid=$!
    else
        API_BASE_URL=$api_base_url "$script" &
        client_pid=$!
    fi
else
    echo ">> stack ready — running playwright project=$project"
    (
        cd gui
        exec env E2E_API_BASE_URL="$api_base_url" npm exec -- playwright test \
            -c playwright.config.ts --project="$project"
    ) &
    client_pid=$!
fi

watched_pids=("$client_pid" "$api_pid" "${agent_pids[@]}")
finished_pid=
if wait -n -p finished_pid "${watched_pids[@]}"; then
    finished_status=0
else
    finished_status=$?
fi
if [ "$finished_pid" = "$client_pid" ]; then
    status=$finished_status
    client_pid=
else
    echo "stack process $finished_pid exited during the client run (status $finished_status)" >&2
    status=1
    kill -TERM "$client_pid" 2>/dev/null || true
    wait "$client_pid" 2>/dev/null || true
    client_pid=
fi

echo ">> stopping workbench agent and backend (SIGTERM so coverage can flush)"
stop_stack
trap - EXIT

echo ">> backend coverage ($tier tier: server + $agents agent(s))"
# Fold this tier's per-process files (one per --parallel-mode process:
# the server and each agent) into the tier's single .coverage. No --keep —
# the suffixed files have no reader once merged, and collapsing them leaves
# the tier looking exactly like a single-process pytest tier for the
# cross-tier combine.
COVERAGE_FILE=$coverage_file coverage combine
COVERAGE_FILE=$coverage_file coverage report
# Report through the same make rule the pytest tiers use, so a stack tier
# gets the identical total + per-package breakdown rather than a second,
# drifting variant. All coverage layout lives in mk/be-tests.mk.
make -s be-coverage-report TIER="$tier"

exit "$status"
