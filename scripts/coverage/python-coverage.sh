#!/usr/bin/env bash
# Render or combine the Python coverage tiers produced by pytest and E2E runs.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
data_dir="$root/test-artifacts/coverage/python/data"
html_dir="$root/test-artifacts/coverage/python"
tiers=(unit integration e2e-gui e2e-gui-review demo-gui demo-api demo-gui-code-ocean)
packages=(protocol core supervisor api executor agent)
cd "$root"

usage() {
    echo "usage: ${0##*/} render <tier> | combine" >&2
    exit 2
}

render() {
    local tier=${1:?}
    local coverage_file="$data_dir/$tier/.coverage"

    if [[ ! -f "$coverage_file" ]]; then
        echo "no coverage data for the $tier tier — run it first: one of ${tiers[*]}" >&2
        exit 1
    fi

    COVERAGE_FILE=$coverage_file coverage html -d "$html_dir/$tier" \
        --title "repo2ree — $tier tier, python" >/dev/null
    echo ">> $tier tier, by module"
    for package in "${packages[@]}"; do
        COVERAGE_FILE=$coverage_file coverage html --include="$package/src/*" \
            -d "$html_dir/$tier/by-module/$package" \
            --title "repo2ree — $package ($tier tier, python)" >/dev/null
        printf '   %-12s %s%%\n' "$package" \
            "$(COVERAGE_FILE=$coverage_file coverage report --include="$package/src/*" --format=total)"
    done
    printf '   %-12s %s%%\n' TOTAL \
        "$(COVERAGE_FILE=$coverage_file coverage report --format=total)"
    echo ">> $tier reports: ${html_dir#"$root/"}/$tier (by module: .../by-module/<package>)"
}

combine() {
    local tier combined_dir coverage_file
    local -a files=() included=() missing=()
    shopt -s nullglob

    for tier in "${tiers[@]}"; do
        local -a found=("$data_dir/$tier"/.coverage*)
        if ((${#found[@]})); then
            files+=("${found[@]}")
            included+=("$tier")
        else
            missing+=("$tier")
        fi
    done

    ((${#files[@]})) || {
        echo "no tier has been measured; run e.g. 'just be-unit-tests' first" >&2
        exit 1
    }
    echo ">> combined: ${included[*]}"
    ((${#missing[@]} == 0)) || echo ">> NOT included (never measured on this tree): ${missing[*]}"

    combined_dir="$data_dir/combined"
    rm -rf "$combined_dir"
    mkdir -p "$combined_dir"
    coverage_file="$combined_dir/.coverage"
    COVERAGE_FILE=$coverage_file coverage combine --keep "${files[@]}"
    COVERAGE_FILE=$coverage_file coverage report
    render combined
}

case ${1:-} in
    render)
        (($# == 2)) || usage
        render "$2"
        ;;
    combine)
        (($# == 1)) || usage
        combine
        ;;
    *) usage ;;
esac
