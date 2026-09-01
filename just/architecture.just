# Generated views of the same import graphs enforced by the architecture
# checks. The backend package list comes from pyproject.toml's import-linter
# contracts so adding a governed package cannot silently omit its diagram.
# The two workspace views answer different questions: workspace.svg collapses
# packages to show cross-package layering, while workspace-modules.svg retains
# modules so an individual dependency edge can be traced.

ARCH_ARGS := env("ARGS", "")
GUI_ARGS := env("GUI_ARGS", "")
GUI_COLLAPSE := env("GUI_COLLAPSE", "^src/(core|shell/[^/]+)/")
GUI_CORE_COLLAPSE := env("GUI_CORE_COLLAPSE", "^src/(core/[^/]+|shell/[^/]+)/")

# Generate every backend and GUI architecture diagram.
[group('Diagrams')]
architecture-diagrams: be-graphs be-graph-all gui-graph gui-graph-core

# Generate one backend package graph.
[group('Diagrams')]
be-graph package="repo2ree_core":
    #!/usr/bin/env bash
    set -euo pipefail
    args_text={{ quote(ARCH_ARGS) }}
    args=()
    if [[ -n "$args_text" ]]; then read -r -a args <<< "$args_text"; fi
    mkdir -p {{ quote(ARCH_DIR) }}
    python scripts/diagrams/arch_graph.py {{ quote(package) }} "${args[@]}" -f svg -o {{ quote(ARCH_DIR + "/" + package + ".svg") }}

# Generate a graph for every backend root package.
[group('Diagrams')]
be-graphs:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    args_text={{ quote(ARCH_ARGS) }}
    args=()
    if [[ -n "$args_text" ]]; then read -r -a args <<< "$args_text"; fi
    packages="$(python scripts/diagrams/arch_graph.py --list-packages)"
    test -n "$packages" || {
      echo "no root packages resolved from pyproject.toml [tool.importlinter] — check 'python scripts/diagrams/arch_graph.py --list-packages'" >&2
      exit 1
    }
    for package in $packages; do
      python scripts/diagrams/arch_graph.py "$package" "${args[@]}" -f svg -o {{ quote(ARCH_DIR) }}/"$package".svg
    done

# Generate collapsed and module-level whole-workspace backend graphs.
[group('Diagrams')]
be-graph-all:
    #!/usr/bin/env bash
    set -euo pipefail
    args_text={{ quote(ARCH_ARGS) }}
    args=()
    if [[ -n "$args_text" ]]; then read -r -a args <<< "$args_text"; fi
    mkdir -p {{ quote(ARCH_DIR) }}
    python scripts/diagrams/arch_graph.py --collapse "${args[@]}" -f svg -o {{ quote(ARCH_DIR + "/workspace.svg") }}
    python scripts/diagrams/arch_graph.py --all "${args[@]}" -f svg -o {{ quote(ARCH_DIR + "/workspace-modules.svg") }}

# dependency-cruiser writes DOT before Graphviz runs so a failed cruise cannot
# be hidden by a successful final pipeline command that emits an empty SVG.
# Generate the collapsed GUI dependency graph.
[group('Diagrams')]
gui-graph:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    gui_args_text={{ quote(GUI_ARGS) }}
    gui_args=()
    if [[ -n "$gui_args_text" ]]; then read -r -a gui_args <<< "$gui_args_text"; fi
    collapse=()
    if [[ -n {{ quote(GUI_COLLAPSE) }} ]]; then collapse=(--collapse {{ quote(GUI_COLLAPSE) }}); fi
    cd gui
    npx depcruise src --include-only '^src' --output-type dot "${collapse[@]}" "${gui_args[@]}" --output-to {{ quote("../" + ARCH_DIR + "/gui.dot") }}
    cd ..
    dot -Tsvg -o {{ quote(ARCH_DIR + "/gui.svg") }} {{ quote(ARCH_DIR + "/gui.dot") }}
    rm -f {{ quote(ARCH_DIR + "/gui.dot") }}
    printf 'wrote %s\n' {{ quote(ARCH_DIR + "/gui.svg") }}

# Generate a GUI dependency graph with the functional core expanded.
[group('Diagrams')]
gui-graph-core:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p {{ quote(ARCH_DIR) }}
    gui_args_text={{ quote(GUI_ARGS) }}
    gui_args=()
    if [[ -n "$gui_args_text" ]]; then read -r -a gui_args <<< "$gui_args_text"; fi
    cd gui
    npx depcruise src --include-only '^src' --output-type dot --collapse {{ quote(GUI_CORE_COLLAPSE) }} "${gui_args[@]}" --output-to {{ quote("../" + ARCH_DIR + "/gui-core.dot") }}
    cd ..
    dot -Tsvg -o {{ quote(ARCH_DIR + "/gui-core.svg") }} {{ quote(ARCH_DIR + "/gui-core.dot") }}
    rm -f {{ quote(ARCH_DIR + "/gui-core.dot") }}
    printf 'wrote %s\n' {{ quote(ARCH_DIR + "/gui-core.svg") }}
