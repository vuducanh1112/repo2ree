# Generated views of the same import graphs enforced by the architecture
# checks. The backend package list comes from pyproject.toml's import-linter
# contracts so adding a governed package cannot silently omit its diagram.
# The two workspace views answer different questions: workspace.svg collapses
# packages to show cross-package layering, while workspace-modules.svg retains
# modules so an individual dependency edge can be traced.

DEFAULT_GUI_COLLAPSE := "^src/(core|shell/[^/]+)/"
DEFAULT_GUI_CORE_COLLAPSE := "^src/(core/[^/]+|shell/[^/]+)/"
BACKEND_GRAPH_PACKAGES := "repo2ree_api repo2ree_core repo2ree_docker repo2ree_executor repo2ree_provider_docker repo2ree_protocol repo2ree_supervisor repo2ree_workbench"

# Generate every backend and GUI architecture diagram.
[group('Diagrams')]
generate-architecture-diagrams: generate-backend-graphs generate-backend-workspace-graphs generate-gui-graph generate-gui-core-graph

# Generate one backend package graph.
[group('Diagrams')]
generate-backend-graph package="repo2ree_core":
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    python -m repo2ree_repoview architecture {{ quote(package) }} -f svg -o {{ quote(ARCH_DIR + "/" + package + ".svg") }}
    {{ STAMP_DIAGRAMS }} --by generate-backend-graph {{ quote(ARCH_DIR + "/" + package + ".svg") }}

# Generate a graph for every backend root package.
[group('Diagrams')]
generate-backend-graphs: (generate-backend-graph "repo2ree_api") (generate-backend-graph "repo2ree_core") (generate-backend-graph "repo2ree_docker") (generate-backend-graph "repo2ree_executor") (generate-backend-graph "repo2ree_provider_docker") (generate-backend-graph "repo2ree_protocol") (generate-backend-graph "repo2ree_supervisor") (generate-backend-graph "repo2ree_workbench")
    #!/usr/bin/env bash
    set -euo pipefail
    configured="$(python -m repo2ree_repoview architecture --list-packages)"
    test "$configured" = {{ quote(BACKEND_GRAPH_PACKAGES) }} || {
      echo "generate-backend-graphs dependencies differ from pyproject.toml [tool.importlinter].root_packages" >&2
      echo "configured: $configured" >&2
      echo "recipes:    " {{ quote(BACKEND_GRAPH_PACKAGES) }} >&2
      exit 1
    }

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
