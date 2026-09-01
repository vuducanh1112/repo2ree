#!/usr/bin/env bash
# Tag and push the protocol-compatible local image set under one candidate tag.
set -euo pipefail

if (($# != 1)); then
    echo "usage: ${0##*/} <candidate-tag>" >&2
    exit 2
fi

tag=$1
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

images=(repo2ree-gui repo2ree-backend repo2ree-agent)
for registry in "${registries[@]}"; do
    for image in "${images[@]}"; do
        docker tag "$image:local" "$registry/$image:$tag"
        docker push "$registry/$image:$tag"
    done
done
