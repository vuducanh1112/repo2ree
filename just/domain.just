DEFAULT_FILMSTRIP_CAPTURE := "test-artifacts/ree-snapshots/api-integration/test_full_authoring_pipeline.ndjson"

# These views consume the real API integration capture rather than fixtures, so
# a missing capture fails with the producing tier instead of drawing an empty or
# stale model.

# Generate every domain-model view.
[group('Diagrams')]
domain-diagrams capture=DEFAULT_FILMSTRIP_CAPTURE: evidence-graph (ree-filmstrip capture) (ree-timeline capture) (ree-browser capture)

# Generate the evidence graph when its inputs changed.
[group('Diagrams')]
evidence-graph:
    #!/usr/bin/env bash
    set -euo pipefail
    output={{ quote(DOMAIN_DIR + "/evidence.svg") }}
    rules='core/src/repo2ree_core/domain/ree/audit.py'
    renderer='scripts/diagrams/evidence_graph.py'
    if [[ ! -e "$output" || "$rules" -nt "$output" || "$renderer" -nt "$output" ]]; then
      mkdir -p {{ quote(DOMAIN_DIR) }}
      python "$renderer" -o "$output"
    fi

[private]
_require-filmstrip-capture capture:
    @test -f {{ quote(capture) }} || { printf 'no capture at %s\n' {{ quote(capture) }} >&2; echo "run: just e2e-bundles && pytest api/tests/integration" >&2; exit 1; }
    @mkdir -p {{ quote(DOMAIN_DIR) }}

# Render audit state across every captured authoring stage.
[group('Diagrams')]
ree-filmstrip capture=DEFAULT_FILMSTRIP_CAPTURE: (_require-filmstrip-capture capture)
    python scripts/diagrams/ree_filmstrip.py --frames {{ quote(capture) }} -o {{ quote(DOMAIN_DIR + "/ree-filmstrip.svg") }}

# Render every aggregate field changed by each authoring stage.
[group('Diagrams')]
ree-timeline capture=DEFAULT_FILMSTRIP_CAPTURE: (_require-filmstrip-capture capture)
    python scripts/diagrams/ree_filmstrip.py -f timeline --frames {{ quote(capture) }} -o {{ quote(DOMAIN_DIR + "/ree-timeline.html") }}

# Render the finished aggregate as browsable HTML.
[group('Diagrams')]
ree-browser capture=DEFAULT_FILMSTRIP_CAPTURE: (_require-filmstrip-capture capture)
    python scripts/diagrams/ree_filmstrip.py -f browse --frames {{ quote(capture) }} -o {{ quote(DOMAIN_DIR + "/ree-browser.html") }}
