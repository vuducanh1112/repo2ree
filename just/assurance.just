# Assurance collects evidence, checks specifications, and presents results.
# History is its current implementation package, separate from the backend.
[group('Assurance')]
check-assurance: check-history

[group('Assurance')]
test-assurance: test-history

# System evidence tooling has independent checks and test artifacts.
ASSURANCE_METRIC_PATHS := "history/src"

[group('Assurance')]
check-history: (_check-python-package "history")
    lint-imports --config history/pyproject.toml

# Run history tests without contributing to backend coverage.
[group('Assurance')]
test-history:
    mkdir -p {{ quote(ASSURANCE_DIR + "/coverage/data") }}
    COVERAGE_FILE={{ quote(ASSURANCE_DIR + "/coverage/data/.coverage") }} pytest history/tests --cov-config=history/pyproject.toml --cov --cov-report=html:{{ quote(ASSURANCE_DIR + "/coverage/html") }} --cov-report=

[group('Assurance')]
generate-assurance-metrics:
    mkdir -p {{ quote(ASSURANCE_DIR + "/reports/metrics") }}
    lizard -l python -i -1 -o {{ quote(ASSURANCE_DIR + "/reports/metrics/complexity.html") }} {{ ASSURANCE_METRIC_PATHS }}
    lizard -l python -i -1 --csv {{ ASSURANCE_METRIC_PATHS }} > {{ quote(ASSURANCE_DIR + "/reports/metrics/complexity.csv") }}


# Generate the history views independently of backend domain diagrams.
[group('Assurance')]
generate-assurance-diagrams: generate-ree-filmstrip generate-ree-timeline generate-ree-browser generate-journals

DEFAULT_FILMSTRIP_CAPTURE := ""

[private]
_require-filmstrip-capture capture:
    @test -f {{ if capture == "" { '"$(python -m test_support.artifacts latest-test test_full_authoring_pipeline state.ndjson)"' } else { quote(capture) } }} || { printf 'no capture at %s\n' {{ if capture == "" { '"$(python -m test_support.artifacts latest-test test_full_authoring_pipeline state.ndjson)"' } else { quote(capture) } }} >&2; echo "run: just build-e2e-bundles && pytest api/tests/integration" >&2; exit 1; }
    @mkdir -p {{ quote(ASSURANCE_DIR) }}

# Render audit state across every captured authoring stage.
[group('Assurance')]
generate-ree-filmstrip capture=DEFAULT_FILMSTRIP_CAPTURE: (_require-filmstrip-capture capture)
    python -m repo2ree_history ree-filmstrip --frames {{ if capture == "" { '"$(python -m test_support.artifacts latest-test test_full_authoring_pipeline state.ndjson)"' } else { quote(capture) } }} -o {{ quote(ASSURANCE_DIR + "/ree-filmstrip.svg") }}

# Render every aggregate field changed by each authoring stage.
[group('Assurance')]
generate-ree-timeline capture=DEFAULT_FILMSTRIP_CAPTURE: (_require-filmstrip-capture capture)
    python -m repo2ree_history ree-filmstrip -f timeline --frames {{ if capture == "" { '"$(python -m test_support.artifacts latest-test test_full_authoring_pipeline state.ndjson)"' } else { quote(capture) } }} -o {{ quote(ASSURANCE_DIR + "/ree-timeline.html") }}

# Render the finished aggregate as browsable HTML.
[group('Assurance')]
generate-ree-browser capture=DEFAULT_FILMSTRIP_CAPTURE: (_require-filmstrip-capture capture)
    python -m repo2ree_history ree-filmstrip -f browse --frames {{ if capture == "" { '"$(python -m test_support.artifacts latest-test test_full_authoring_pipeline state.ndjson)"' } else { quote(capture) } }} -o {{ quote(ASSURANCE_DIR + "/ree-browser.html") }}
