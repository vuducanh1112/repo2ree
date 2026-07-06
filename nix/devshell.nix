# ----------------------------------------------------------------
# Developer shell
#
# Tooling for working on repo2ree locally (frontend, CLI, k8s). This
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
    nodejs_25
    python313Packages.uv
    kubectl

    # graphviz for generating graphs with dependency cruiser
    graphviz

    # vale lints prose in docs/ (config in ./.vale.ini)
    vale

    # static analyser for shell scripts
    shellcheck

    # playwright browser drivers, because using nix and using playwright via npm does not work, since playwright
    # looks at default locations
    # fonts are important for the browsers to render properly
    playwright-driver.browsers
    fontconfig
    dejavu_fonts

  ];

  shellHook = ''
    if [ -t 1 ]; then
      echo "❄️  Nix Shell Loaded"
      echo "Node: $(node -v) | uv: $(uv --version) | kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
      export PS1="\[\033[1;34m\][nix-shell]\[\033[0m\] \w $ " # custom the shell prompt
    fi

    export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}
    export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="${pkgs.playwright-driver.browsers}/chromium_headless_shell-1200/chrome-linux/headless_shell"
    export FONTCONFIG_FILE=${pkgs.makeFontsConf { fontDirectories = [ pkgs.dejavu_fonts ]; }}
  '';
}
