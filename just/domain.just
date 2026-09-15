# Generate static domain-model views.
[group('Diagrams')]
generate-domain-diagrams: generate-evidence-graph

# Generate the evidence graph when its inputs changed.
[group('Diagrams')]
generate-evidence-graph:
    #!/usr/bin/env bash
    set -euo pipefail
    output={{ quote(DOMAIN_DIR + "/evidence.svg") }}
    rules='core/src/repo2ree_core/domain/ree/audit.py'
    renderer='scripts/diagrams/evidence_graph.py'
    if [[ ! -e "$output" || "$rules" -nt "$output" || "$renderer" -nt "$output" ]]; then
      mkdir -p {{ quote(DOMAIN_DIR) }}
      python "$renderer" -o "$output"
    fi
