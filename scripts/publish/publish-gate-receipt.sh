#!/usr/bin/env bash
# Record and verify the exact clean tree and local image set exercised by
# `just publish-gate`. Publishing reads image IDs from this receipt rather than
# mutable :local tags, so it pushes precisely what the gate tested.
set -euo pipefail

images=(repo2ree-gui repo2ree-backend repo2ree-provider-docker)

usage() {
    echo "usage: ${0##*/} {write|verify} <receipt> <revision>" >&2
    exit 2
}

image_id() {
    docker image inspect --format '{{.Id}}' "$1"
}

assert_ignored() {
    local receipt=$1
    if ! git check-ignore -q "$receipt"; then
        echo "refusing to write a publish-gate receipt not ignored by git: $receipt" >&2
        exit 1
    fi
}

write_receipt() {
    local receipt=$1 revision=$2 image id pending
    mkdir -p "$(dirname "$receipt")"
    assert_ignored "$receipt"
    pending="$receipt.pending"
    trap 'rm -f "$pending"' RETURN
    {
        printf 'revision\t%s\n' "$revision"
        printf 'tree\t%s\n' "$(git write-tree)"
        for image in "${images[@]}"; do
            id=$(image_id "$image:local")
            [[ $id =~ ^sha256:[0-9a-f]{64}$ ]] || {
                echo "invalid local image ID for $image:local: $id" >&2
                exit 1
            }
            printf 'image\t%s\t%s\n' "$image" "$id"
        done
    } >"$pending"
    mv "$pending" "$receipt"
    trap - RETURN
}

verify_receipt() {
    local receipt=$1 revision=$2 recorded image expected current
    [[ -f $receipt ]] || {
        echo "no publish-gate receipt for this clone — run: just publish-gate" >&2
        exit 1
    }
    recorded=$(awk '$1 == "revision" { print $2 }' "$receipt")
    [[ $recorded == "$revision" ]] || {
        echo "publish-gate receipt names revision $recorded, expected $revision" >&2
        exit 1
    }
    recorded=$(awk '$1 == "tree" { print $2 }' "$receipt")
    [[ $recorded == "$(git write-tree)" ]] || {
        echo "publish-gate receipt covers different repository content" >&2
        exit 1
    }
    for image in "${images[@]}"; do
        expected=$(awk -v image="$image" '$1 == "image" && $2 == image { print $3 }' "$receipt")
        [[ $expected =~ ^sha256:[0-9a-f]{64}$ ]] || {
            echo "publish-gate receipt is missing a valid ID for $image" >&2
            exit 1
        }
        current=$(image_id "$image:local")
        [[ $current == "$expected" ]] || {
            echo "$image:local changed after publish-gate: $current, expected $expected" >&2
            exit 1
        }
    done
}

(($# == 3)) || usage
case "$1" in
write) write_receipt "$2" "$3" ;;
verify) verify_receipt "$2" "$3" ;;
*) usage ;;
esac
