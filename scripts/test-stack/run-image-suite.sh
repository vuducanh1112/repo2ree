#!/usr/bin/env bash
# Own an image-backed stack for one browser suite or API walkthrough.
set -euo pipefail

if (($# < 2 || $# > 4)); then
    echo "usage: ${0##*/} <suite> <agents> [image-repository image-tag]" >&2
    exit 2
fi

suite=$1
agents=$2
image_repository=${3:-}
image_tag=${4:-}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
stack="$root/scripts/test-stack/image-stack.sh"

[[ $agents =~ ^[1-9][0-9]*$ ]] || {
    echo "agents must be a positive integer" >&2
    exit 2
}
if { [[ -n $image_repository ]] && [[ -z $image_tag ]]; } || \
    { [[ -z $image_repository ]] && [[ -n $image_tag ]]; }; then
    echo "image repository and tag must be provided together" >&2
    exit 2
fi

cleanup() { "$stack" down --volumes; }
trap cleanup EXIT
cd "$root"

if [[ -n $image_repository ]]; then
    STACK_IMAGE_REPO=$image_repository STACK_IMAGE_TAG=$image_tag STACK_AGENTS=$agents "$stack" up
else
    STACK_AGENTS=$agents "$stack" up
fi
"$stack" check

if [[ $suite == demo-api ]]; then
    API_BASE_URL=$("$stack" api-url) api/tests/e2e/api_agent_walkthrough.py
else
    cd gui
    E2E_BASE_URL=$("$stack" gui-url) npm exec -- playwright test \
        -c playwright.config.ts --project="$suite"
fi

cleanup
trap - EXIT
