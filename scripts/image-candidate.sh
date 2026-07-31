#!/usr/bin/env bash
# A validation receipt is one revision line followed by sorted image rows:
#   revision <git-rev>
#   image <registry> <name> <sha256:digest>
# Its existence means validate-image-candidate completed both e2e suites.
set -euo pipefail

images=(repo2ree-agent repo2ree-backend repo2ree-gui)

usage() {
	echo "usage: ${0##*/} {resolve <rev> <receipt> <registry>...|environment <receipt> <registry>|verify <rev> <receipt>|promote <rev> <receipt>}" >&2
	exit 2
}

resolve_digest() {
	local reference=$1 digest
	digest=$(docker buildx imagetools inspect "$reference" \
		| awk '/^Digest:/ { print $2 }')
	[[ $digest =~ ^sha256:[0-9a-f]{64}$ ]] || {
		echo "invalid manifest digest for $reference: $digest" >&2
		exit 1
	}
	printf '%s\n' "$digest"
}

receipt_digest() {
	local receipt=$1 registry=$2 image=$3
	awk -v registry="$registry" -v image="$image" \
		'$1 == "image" && $2 == registry && $3 == image { print $4 }' "$receipt"
}

resolve_candidate() {
	local revision=$1 receipt=$2
	shift 2
	local registry image digest expected rows

	[[ $revision =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] || usage
	(($# > 0)) || usage
	mkdir -p "$(dirname "$receipt")"
	git check-ignore -q "$receipt" || {
		echo "refusing to write a validation receipt not ignored by git: $receipt" >&2
		exit 1
	}
	rows=$(mktemp)
	trap 'rm -f "$rows"' EXIT

	for image in "${images[@]}"; do
		expected=
		for registry in "$@"; do
			digest=$(resolve_digest "$registry/$image:$revision")
			[[ -z $expected || $digest == "$expected" ]] || {
				echo "registries disagree for $image: $expected != $digest" >&2
				exit 1
			}
			expected=$digest
			printf 'image\t%s\t%s\t%s\n' "$registry" "$image" "$digest" >>"$rows"
		done
	done

	{
		printf 'revision\t%s\n' "$revision"
		sort "$rows"
	} >"$receipt"
	rm -f "$rows"
	trap - EXIT
}

receipt_registries() {
	awk '$1 == "image" { print $2 }' "$1" | sort -u
}

verify_candidate() {
	local revision=$1 receipt=$2 registry image digest current
	local found_registry=false

	[[ -f $receipt ]] || {
		echo "no validation receipt for image candidate $revision: $receipt" >&2
		exit 1
	}
	[[ $(awk '$1 == "revision" { print $2 }' "$receipt") == "$revision" ]] || {
		echo "validation receipt does not name image candidate $revision" >&2
		exit 1
	}
	while IFS= read -r registry; do
		[[ -n $registry ]] || continue
		found_registry=true
		for image in "${images[@]}"; do
			digest=$(receipt_digest "$receipt" "$registry" "$image")
			[[ $digest =~ ^sha256:[0-9a-f]{64}$ ]] || {
				echo "validation receipt is missing $registry/$image" >&2
				exit 1
			}
			current=$(resolve_digest "$registry/$image:$revision")
			[[ $current == "$digest" ]] || {
				echo "$registry/$image:$revision changed: $current, expected $digest" >&2
				exit 1
			}
		done
	done < <(receipt_registries "$receipt")
	[[ $found_registry == true ]] || { echo "validation receipt contains no images" >&2; exit 1; }
}

print_environment() {
	local receipt=$1 registry=$2 image digest variable
	for image in "${images[@]}"; do
		digest=$(receipt_digest "$receipt" "$registry" "$image")
		[[ -n $digest ]] || { echo "$registry/$image is not in $receipt" >&2; exit 1; }
		case "$image" in
		repo2ree-agent) variable=STACK_AGENT_IMAGE ;;
		repo2ree-backend) variable=STACK_BACKEND_IMAGE ;;
		repo2ree-gui) variable=STACK_GUI_IMAGE ;;
		esac
		printf '%s=%q\n' "$variable" "$registry/$image@$digest"
	done
}

promote_candidate() {
	local revision=$1 receipt=$2 registry image digest target
	verify_candidate "$revision" "$receipt"
	while IFS= read -r registry; do
		[[ -n $registry ]] || continue
		for image in "${images[@]}"; do
			digest=$(receipt_digest "$receipt" "$registry" "$image")
			target="$registry/$image:edge"
			echo ">> $target: $digest"
			docker buildx imagetools create --prefer-index=false \
				-t "$target" "$registry/$image@$digest"
			[[ $(resolve_digest "$target") == "$digest" ]] || {
				echo "promotion verification failed for $target" >&2
				exit 1
			}
		done
	done < <(receipt_registries "$receipt")
}

case "${1:-}" in
resolve) (($# >= 4)) || usage; resolve_candidate "$2" "$3" "${@:4}" ;;
environment) (($# == 3)) || usage; print_environment "$2" "$3" ;;
verify) (($# == 3)) || usage; verify_candidate "$2" "$3" ;;
promote) (($# == 3)) || usage; promote_candidate "$2" "$3" ;;
*) usage ;;
esac
