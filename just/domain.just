# Draw the behaviour specification's machines: the system map, each machine as allowed and as the
# assurance-gate receipt's tests and the showcases' took it (as this tree judges them), each part of an aggregate with the operations that moved it, and each aggregate's evidence graph.
[group('Diagrams')]
generate-spec-diagrams: export-spec (assess-behaviour "") visualize-showcases
    #!/usr/bin/env bash
    set -euo pipefail
    written=$(python -m repo2ree_repoview spec-diagrams --spec {{ quote(EXPORT_DIR + "/spec.json") }} -o {{ quote(DIAGRAM_DIR + "/spec") }})
    mapfile -t drawings <<< "$written"
    {{ STAMP_DIAGRAMS }} --by generate-spec-diagrams "${drawings[@]}"
