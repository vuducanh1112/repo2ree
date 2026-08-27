# ----------------------------------------------------------------
# Developer shell
#
# Tooling for working on repo2ree locally (GUI, CLI, k8s). This
# is intentionally separate from the shipped closures (./ree-executor.nix,
# ./tools.nix): edits here are routine and must never touch the
# reproducibility-sensitive surfaces.
#
# Enter with:   nix develop
# ----------------------------------------------------------------
{ pkgs }:

pkgs.mkShell {
  buildInputs = with pkgs; [

    # Essentials
    git
    less
    vim
    docker-client
    ps

    # Project
    nodejs_24
    python313Packages.uv
    kubectl

    # graphviz for generating graphs with dependency cruiser
    graphviz

    # Documentation: Vale lints prose, Lychee validates links and fragments,
    # and Zensical builds the public Markdown tree into a static website.
    vale
    lychee
    zensical

    # static analyser for shell scripts
    shellcheck

    # asciinema records the pure-API agent walkthrough (api/tests/e2e/
    # api_agent_walkthrough.py) as a terminal .cast; agg renders that .cast to an
    # SVG/GIF artifact. The walkthrough itself is stdlib-only python — no client
    # dependency to add here.
    asciinema
    asciinema-agg

    # nix linting: antipatterns (statix) and unused bindings (deadnix);
    # formatting goes through `nix fmt` (see formatter in ../flake.nix)
    statix
    deadnix

    # playwright browser drivers, because using nix and using playwright via npm does not work, since playwright
    # looks at default locations
    # fonts are important for the browsers to render properly
    playwright-driver.browsers
    fontconfig
    dejavu_fonts

  ];

  shellHook = ''
    # Lizard is a Python application, but only its executable belongs in this
    # full-stack shell. Putting the package in buildInputs would export its
    # Python dependencies through PYTHONPATH, where they can shadow the uv
    # virtualenv (notably pathspec, which mypy also imports). The Nix wrapper
    # on the executable already carries everything Lizard itself needs.
    export PATH="${pkgs.python313Packages.lizard}/bin:$PATH"

    if [ -t 1 ]; then
      echo "❄️  Nix Shell Loaded"
      echo "Node: $(node -v) | uv: $(uv --version) | kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
      export PS1="\[\033[1;34m\][nix-shell]\[\033[0m\] \w $ " # custom the shell prompt
    fi

    export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}

    # The chromium revision directory is named for playwright's own build
    # number, which moves whenever playwright-driver does — it went 1200 ->
    # 1228 on the nixpkgs bump that brought otel 1.43, and a hardcoded number
    # silently points at nothing. Resolve it instead, and say so loudly if the
    # layout ever changes shape, because the alternative is every browser suite
    # failing on a path that looks plausible.
    __shell=(${pkgs.playwright-driver.browsers}/chromium_headless_shell-*/chrome-linux/headless_shell)
    if [ -x "''${__shell[0]}" ]; then
      export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="''${__shell[0]}"
    else
      echo "warning: no chromium_headless_shell under ${pkgs.playwright-driver.browsers}" >&2
    fi
    unset __shell
    export FONTCONFIG_FILE=${pkgs.makeFontsConf { fontDirectories = [ pkgs.dejavu_fonts ]; }}
  '';
}
