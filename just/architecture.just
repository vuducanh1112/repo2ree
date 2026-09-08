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
generate-architecture-diagrams: generate-backend-graphs generate-backend-workspace-graphs generate-gui-graph generate-gui-core-graph generate-just-recipe-graph

# Generate the declared Just recipe dependency graph.
[group('Diagrams')]
generate-just-recipe-graph:
    python scripts/diagrams/just_graph.py -o {{ quote(ARCH_DIR + "/just-recipes.svg") }}

# Generate one backend package graph.
[group('Diagrams')]
generate-backend-graph package="repo2ree_core":
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    python scripts/diagrams/arch_graph.py {{ quote(package) }} -f svg -o {{ quote(ARCH_DIR + "/" + package + ".svg") }}

# Generate a graph for every backend root package.
[group('Diagrams')]
generate-backend-graphs:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    packages="$(python scripts/diagrams/arch_graph.py --list-packages)"
    test -n "$packages" || {
      echo "no root packages resolved from pyproject.toml [tool.importlinter] — check 'python scripts/diagrams/arch_graph.py --list-packages'" >&2
      exit 1
    }
    for package in $packages; do
      python scripts/diagrams/arch_graph.py "$package" -f svg -o {{ quote(ARCH_DIR) }}/"$package".svg
    done

# Generate collapsed and module-level whole-workspace backend graphs.
[group('Diagrams')]
generate-backend-workspace-graphs:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    python scripts/diagrams/arch_graph.py --collapse -f svg -o {{ quote(ARCH_DIR + "/workspace.svg") }}
    python scripts/diagrams/arch_graph.py --all -f svg -o {{ quote(ARCH_DIR + "/workspace-modules.svg") }}

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
    printf 'wrote %s\n' {{ quote(ARCH_DIR + "/gui-core.svg") }}
