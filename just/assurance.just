# Assurance collects evidence, checks specifications, and presents results.
# Conformance checks owner journals, REE histories, and stores against
# specifications/behaviour, separately from the backend it observes.

# Static checks for every assurance package.
[group('Assurance')]
check-assurance: check-conformance

# Tests for every assurance package.
[group('Assurance')]
test-assurance: test-conformance

# System evidence tooling has independent checks and test artifacts.
ASSURANCE_METRIC_PATHS := "conformance/src"

# Static checks, the checker's independence contracts, and a fresh generated machines module.
[group('Assurance')]
check-conformance: (_check-python-package "conformance")
    lint-imports --config conformance/pyproject.toml
    python -m repo2ree_conformance generate --check

# Conformance tests; the system test drives the real owners and needs git.
[group('Assurance')]
test-conformance:
    pytest conformance/tests

# Regenerate protocol's behaviour machines after editing specifications/behaviour.
[group('Assurance')]
generate-behaviour:
    python -m repo2ree_conformance generate

# Check a recording's journals and REE histories against the behaviour specification (exit 0/1/2).
[group('Assurance')]
check-behaviour recording output=(ASSURANCE_DIR + "/behaviour"):
    python -m repo2ree_conformance check --recording {{ quote(recording) }} -o {{ quote(output) }}

[group('Assurance')]
generate-assurance-metrics:
    mkdir -p {{ quote(ASSURANCE_DIR + "/reports/metrics") }}
    lizard -l python -i -1 -o {{ quote(ASSURANCE_DIR + "/reports/metrics/complexity.html") }} {{ ASSURANCE_METRIC_PATHS }}
    lizard -l python -i -1 --csv {{ ASSURANCE_METRIC_PATHS }} > {{ quote(ASSURANCE_DIR + "/reports/metrics/complexity.csv") }}
