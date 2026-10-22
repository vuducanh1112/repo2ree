# ----------------------------------------------------------------
# Developer shell
#
# Tooling for working on repo2ree locally (GUI, CLI, k8s). This
# is intentionally separate from the shipped closures (./ree-executor.nix,
# ./tools.nix): edits here are routine and must never touch the
# reproducibility-sensitive surfaces.
#
# Two package sets, named as in flake.nix: `pkgs` is the pin the closures and
# images build from (nixpkgs), used here only for the toolchains whose version
# must match what ships; `devPkgs` (nixpkgs-dev) supplies every other tool.
#
# Enter with:   nix develop
# ----------------------------------------------------------------
{ pkgs, devPkgs }:

devPkgs.mkShell {
  buildInputs = [
    # The Node the GUI image is built with, and the Python the shipped closures
    # run on; the venv is made from this interpreter (UV_PYTHON below).
    pkgs.nodejs_24
    pkgs.python313
  ]
  ++ (with devPkgs; [

    # Essentials
    git
    git-lfs
    less
    vim
    docker-client
    ps

    # Project
    uv
    kubectl
    just

    # graphviz for generating graphs with dependency cruiser
    graphviz

    # Documentation: Vale lints prose, Lychee validates links and fragments,
    # and Zensical builds the public Markdown tree into a static website.
    vale
    lychee
    zensical
    typst

    # static analyser for shell scripts
    shellcheck

    # Runs the git hooks in .pre-commit-config.yaml; every hook there is a
    # local command, so this is a dispatcher, not a dependency of the code.
    # The hook nixpkgs' pre-commit installs runs it by its store path; .envrc
    # reinstalls the hook when that path is not this shell's.
    pre-commit

    # Cyclomatic complexity for the metrics reports.
    python313Packages.lizard

    # asciinema records the pure-API workbench walkthrough (api/tests/e2e/
    # api_walkthrough.py) as a terminal .cast; agg renders that .cast to an
    # SVG/GIF artifact. The walkthrough itself is stdlib-only python — no client
    # dependency to add here.
    asciinema
    asciinema-agg

    # nix formatting and linting. `nix fmt` remains the writing interface;
    # checks call nixfmt directly because treefmt has no non-writing mode.
    nixfmt
    statix
    deadnix

    # playwright browser drivers, because using nix and using playwright via npm does not work, since playwright
    # looks at default locations
    # fonts are important for the browsers to render properly
    playwright-driver.browsers
    fontconfig
    dejavu_fonts

  ]);

  shellHook = ''
    export UV_PYTHON=${pkgs.python313}/bin/python3.13
    export UV_PYTHON_DOWNLOADS=never

    # Python applications above (zensical, lizard) export their own
    # dependencies through PYTHONPATH, where the venv's interpreter would import
    # them ahead of uv.lock's: click, pygments, pyyaml, pytest. Their wrapped
    # executables carry their own paths, so the shell exports none.
    unset PYTHONPATH

    if [ -t 1 ]; then
      echo "❄️  Nix Shell Loaded"
      echo "Node: $(node -v) | uv: $(uv --version) | kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
      export PS1="\[\033[1;34m\][nix-shell]\[\033[0m\] \w $ " # custom the shell prompt
    fi

    export PLAYWRIGHT_BROWSERS_PATH=${devPkgs.playwright-driver.browsers}

    # The chromium revision directory is named for playwright's own build
    # number, which moves whenever playwright-driver does — it went 1200 ->
    # 1228 -> 1248 — and the directory under it names the platform
    # (chrome-headless-shell-linux-arm64 since 1.64; chrome-linux before), so a
    # hardcoded path silently points at nothing. Resolve it instead, and say so
    # loudly if the layout ever changes shape, because the alternative is every
    # browser suite failing on a path that looks plausible.
    __shell=(${devPkgs.playwright-driver.browsers}/chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell)
    if [ -x "''${__shell[0]}" ]; then
      export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="''${__shell[0]}"
    else
      echo "warning: no chromium_headless_shell under ${devPkgs.playwright-driver.browsers}" >&2
    fi
    unset __shell
    export FONTCONFIG_FILE=${devPkgs.makeFontsConf { fontDirectories = [ devPkgs.dejavu_fonts ]; }}
  '';
}
