#!/usr/bin/env bash
# Own an image-backed stack for one browser suite or API walkthrough.
set -euo pipefail

usage() {
    echo "usage: ${0##*/} --suite NAME --workbenches N --images local|published" >&2
    echo "       [--repository REPOSITORY --tag TAG]" >&2
    exit 2
}

suite=
workbenches=
images=local
image_repository=
image_tag=
while (($#)); do
    case "$1" in
        --suite) (($# >= 2)) || usage; suite=$2; shift 2 ;;
        --workbenches) (($# >= 2)) || usage; workbenches=$2; shift 2 ;;
        --images) (($# >= 2)) || usage; images=$2; shift 2 ;;
        --repository) (($# >= 2)) || usage; image_repository=$2; shift 2 ;;
        --tag) (($# >= 2)) || usage; image_tag=$2; shift 2 ;;
        *) usage ;;
    esac
done
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
stack="$root/scripts/test-stack/image-stack.sh"

[[ -n $suite ]] || usage
[[ $workbenches =~ ^[1-9][0-9]*$ ]] || {
    echo "workbenches must be a positive integer" >&2
    exit 2
}
case "$images" in
    local)
        if [[ -n $image_repository || -n $image_tag ]]; then
            echo "--repository and --tag apply only to --images published" >&2
            exit 2
        fi
        ;;
    published)
        if [[ -z $image_repository || -z $image_tag ]]; then
            echo "--images published requires --repository and --tag" >&2
            exit 2
        fi
        ;;
    *) usage ;;
esac

cleanup() { "$stack" down --volumes; }
trap cleanup EXIT
cd "$root"

up_args=(--providers "$workbenches")
if [[ $images == published ]]; then
    up_args+=(--image-repository "$image_repository" --image-tag "$image_tag")
fi
"$stack" up "${up_args[@]}"
"$stack" check

if [[ $suite == demo-api ]]; then
    API_BASE_URL=$("$stack" api-url) api/tests/e2e/api_walkthrough.py
else
    cd gui
    E2E_BASE_URL=$("$stack" gui-url) npm exec -- playwright test \
        -c playwright.config.ts --project="$suite"
fi

cleanup
trap - EXIT
