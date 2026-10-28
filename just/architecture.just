# Generated views of the same import graphs enforced by the architecture
# checks. The backend package list comes from pyproject.toml's import-linter
# contracts so adding a governed package cannot silently omit its diagram.
# The two workspace views answer different questions: workspace.svg collapses
# packages to show cross-package layering, while workspace-modules.svg retains
# modules so an individual dependency edge can be traced.

DEFAULT_GUI_COLLAPSE := "^src/(core|shell/[^/]+)/"
DEFAULT_GUI_CORE_COLLAPSE := "^src/(core/[^/]+|shell/[^/]+)/"

# Generate every backend and GUI architecture diagram.
[group('Diagrams')]
generate-architecture-diagrams: generate-backend-graphs generate-backend-workspace-graphs generate-gui-graph generate-gui-core-graph

# Generate backend package graphs (e.g. `just generate-backend-graph repo2ree_api`).
[group('Diagrams')]
generate-backend-graph +packages="repo2ree_core":
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    for package in {{ packages }}; do
        python -m repo2ree_repoview architecture "$package" -f svg -o {{ quote(ARCH_DIR) }}/"$package".svg
        {{ STAMP_DIAGRAMS }} --by generate-backend-graph {{ quote(ARCH_DIR) }}/"$package".svg
    done

# Generate a graph for every backend root package.
[group('Diagrams')]
generate-backend-graphs: (generate-backend-graph `python -m repo2ree_repoview architecture --list-packages`)

# Generate collapsed and module-level whole-workspace backend graphs.
[group('Diagrams')]
generate-backend-workspace-graphs:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    python -m repo2ree_repoview architecture --collapse -f svg -o {{ quote(ARCH_DIR + "/workspace.svg") }}
    python -m repo2ree_repoview architecture --all -f svg -o {{ quote(ARCH_DIR + "/workspace-modules.svg") }}
    {{ STAMP_DIAGRAMS }} --by generate-backend-workspace-graphs {{ quote(ARCH_DIR + "/workspace.svg") }} {{ quote(ARCH_DIR + "/workspace-modules.svg") }}

# dependency-cruiser writes DOT before Graphviz runs so a failed cruise cannot
# be hidden by a successful final pipeline command that emits an empty SVG.
# Generate the collapsed GUI dependency graph.
[group('Diagrams')]
generate-gui-graph collapse=DEFAULT_GUI_COLLAPSE:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    collapse=()
    if [[ -n {{ quote(collapse) }} ]]; then collapse=(--collapse {{ quote(collapse) }}); fi
    cd gui
    npx depcruise src --include-only '^src' --output-type dot "${collapse[@]}" --output-to {{ quote("../" + ARCH_DIR + "/gui.dot") }}
    cd ..
    dot -Tsvg -o {{ quote(ARCH_DIR + "/gui.svg") }} {{ quote(ARCH_DIR + "/gui.dot") }}
    rm -f {{ quote(ARCH_DIR + "/gui.dot") }}
    {{ STAMP_DIAGRAMS }} --by generate-gui-graph {{ quote(ARCH_DIR + "/gui.svg") }}
    printf 'wrote %s\n' {{ quote(ARCH_DIR + "/gui.svg") }}

# Generate a GUI dependency graph with the functional core expanded.
[group('Diagrams')]
generate-gui-core-graph collapse=DEFAULT_GUI_CORE_COLLAPSE:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    cd gui
    npx depcruise src --include-only '^src' --output-type dot --collapse {{ quote(collapse) }} --output-to {{ quote("../" + ARCH_DIR + "/gui-core.dot") }}
    cd ..
    dot -Tsvg -o {{ quote(ARCH_DIR + "/gui-core.svg") }} {{ quote(ARCH_DIR + "/gui-core.dot") }}
    rm -f {{ quote(ARCH_DIR + "/gui-core.dot") }}
    {{ STAMP_DIAGRAMS }} --by generate-gui-core-graph {{ quote(ARCH_DIR + "/gui-core.svg") }}
    printf 'wrote %s\n' {{ quote(ARCH_DIR + "/gui-core.svg") }}
