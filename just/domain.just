# Draw the behaviour specification's machines: the system map, each machine as allowed and as the
# assurance-gate receipt's tests took it (as this tree judges them), and each part of an aggregate with the operations that moved it.
[group('Diagrams')]
generate-spec-diagrams: export-spec (assess-behaviour "")
    #!/usr/bin/env bash
    set -euo pipefail
    written=$(python -m repo2ree_repoview spec-diagrams --spec {{ quote(EXPORT_DIR + "/spec.json") }} -o {{ quote(DIAGRAM_DIR + "/spec") }})
    mapfile -t drawings <<< "$written"
    {{ STAMP_DIAGRAMS }} --by generate-spec-diagrams "${drawings[@]}"

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
    renderer='repoview/src/repo2ree_repoview/diagrams/evidence.py'
    if [[ ! -e "$output" || "$rules" -nt "$output" || "$renderer" -nt "$output" ]]; then
      mkdir -p {{ quote(DOMAIN_DIR) }}
      python -m repo2ree_repoview evidence -o "$output"
      {{ STAMP_DIAGRAMS }} --by generate-evidence-graph "$output"
    fi
