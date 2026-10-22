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

    # Lizard is a Python application, but only its executable belongs in this
    # full-stack shell. Putting the package in buildInputs would export its
    # Python dependencies through PYTHONPATH, where they can shadow the uv
    # virtualenv (notably pathspec, which mypy also imports). The Nix wrapper
    # on the executable already carries everything Lizard itself needs.
    export PATH="${devPkgs.python313Packages.lizard}/bin:$PATH"

    if [ -t 1 ]; then
      echo "❄️  Nix Shell Loaded"
      echo "Node: $(node -v) | uv: $(uv --version) | kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
      export PS1="\[\033[1;34m\][nix-shell]\[\033[0m\] \w $ " # custom the shell prompt
    fi

    export PLAYWRIGHT_BROWSERS_PATH=${devPkgs.playwright-driver.browsers}

    # The chromium revision directory is named for playwright's own build
    # number, which moves whenever playwright-driver does — it went 1200 ->
    # 1228 on the nixpkgs bump that brought otel 1.43, and a hardcoded number
    # silently points at nothing. Resolve it instead, and say so loudly if the
    # layout ever changes shape, because the alternative is every browser suite
    # failing on a path that looks plausible.
    __shell=(${devPkgs.playwright-driver.browsers}/chromium_headless_shell-*/chrome-linux/headless_shell)
    if [ -x "''${__shell[0]}" ]; then
      export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="''${__shell[0]}"
    else
      echo "warning: no chromium_headless_shell under ${devPkgs.playwright-driver.browsers}" >&2
    fi
    unset __shell
    export FONTCONFIG_FILE=${devPkgs.makeFontsConf { fontDirectories = [ devPkgs.dejavu_fonts ]; }}
  '';
}
