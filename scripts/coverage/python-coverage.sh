#!/usr/bin/env bash
# Render or combine the Python coverage tiers produced by pytest and E2E runs.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
data_dir="$root/test-artifacts/coverage/python/data"
html_dir="$root/test-artifacts/coverage/python"
tiers=(unit integration e2e-gui e2e-gui-review demo-gui demo-api demo-gui-code-ocean)
# The workspace members, in pyproject's order. A package missing here is not
# measured any less — it just never gets its own by-module report, which is how
# `provider` and `docker-support` went unreported when they were split out.
packages=(protocol core supervisor api executor docker-support provider workbench)
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
        printf '   %-15s %s%%\n' "$package" \
            "$(COVERAGE_FILE=$coverage_file coverage report --include="$package/src/*" --format=total)"
    done
    printf '   %-15s %s%%\n' TOTAL \
        "$(COVERAGE_FILE=$coverage_file coverage report --format=total)"
    echo ">> $tier reports: ${html_dir#"$root/"}/$tier (by module: .../by-module/<package>)"
}

# A tier measured before a package was moved or renamed records source files
# that no longer exist. coverage's report fails on the first missing source,
# which is the *right* instinct: such a tier does not describe this tree, and
# blending it in would credit a combined total with lines from a package that
# is gone. Excluding it by name beats both crashing and silently ignoring it.
tier_matches_tree() {
    python3 - "$1" <<'PY'
import pathlib
import sys

from coverage import CoverageData

for data_file in sorted(pathlib.Path(sys.argv[1]).glob(".coverage*")):
    data = CoverageData(basename=str(data_file))
    data.read()
    if any(not pathlib.Path(measured).exists() for measured in data.measured_files()):
        sys.exit(1)
sys.exit(0)
PY
}

combine() {
    local tier combined_dir coverage_file
    local -a files=() included=() missing=() stale=()
    shopt -s nullglob

    for tier in "${tiers[@]}"; do
        local -a found=("$data_dir/$tier"/.coverage*)
        if ((${#found[@]} == 0)); then
            missing+=("$tier")
        elif tier_matches_tree "$data_dir/$tier"; then
            files+=("${found[@]}")
            included+=("$tier")
        else
            stale+=("$tier")
        fi
    done

    ((${#files[@]})) || {
        echo "no tier has been measured; run e.g. 'just be-unit-tests' first" >&2
        exit 1
    }
    echo ">> combined: ${included[*]}"
    ((${#missing[@]} == 0)) || echo ">> NOT included (never measured on this tree): ${missing[*]}"
    ((${#stale[@]} == 0)) || {
        echo ">> NOT included (measured against an older tree — re-run to refresh): ${stale[*]}"
    }

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
