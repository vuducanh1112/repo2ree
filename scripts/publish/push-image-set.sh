#!/usr/bin/env bash
# Tag and push the protocol-compatible local image set under one candidate tag.
set -euo pipefail

if (($# < 1 || $# > 2)); then
    echo "usage: ${0##*/} <candidate-tag> [publish-gate-receipt]" >&2
    exit 2
fi

tag=$1
receipt=${2:-}
case $tag in
    '' | edge)
        echo "image-set pushes require a non-edge candidate tag; edge moves only through validated promotion" >&2
        exit 1
        ;;
esac

registries_text=${REGISTRIES:-}
read -r -a registries <<<"$registries_text"
((${#registries[@]})) || {
    echo "REGISTRIES must name at least one registry namespace" >&2
    exit 2
}

images=(repo2ree-gui repo2ree-backend repo2ree-provider-docker)
for registry in "${registries[@]}"; do
    for image in "${images[@]}"; do
        source="$image:local"
        if [[ -n $receipt ]]; then
            source=$(awk -v image="$image" '$1 == "image" && $2 == image { print $3 }' "$receipt")
            [[ $source =~ ^sha256:[0-9a-f]{64}$ ]] || {
                echo "publish-gate receipt is missing a valid ID for $image" >&2
                exit 1
            }
        fi
        docker tag "$source" "$registry/$image:$tag"
        docker push "$registry/$image:$tag"
    done
done
