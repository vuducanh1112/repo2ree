{
  description = "Fullstack Dev Environment with Node 25, UV, and Kubectl";

  inputs = {
    # Nixpkgs unstable usually carries the latest Node versions
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          #config.allowUnfree = true; # Needed for some kubectl plugins/drivers
        };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [

            # Essentials
            git
            less
            vim
            docker-client

            # Project
            nodejs_25        
            python313Packages.uv
            kubectl

            renovate
          ];

          shellHook = ''
            if [ -t 1 ]; then
              echo "❄️  Nix Shell Loaded"
              echo "Node: $(node -v) | uv: $(uv --version) | kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
              export PS1="\[\033[1;34m\][nix-shell]\[\033[0m\] \w $ " # custom the shell prompt
            fi
          '';
        };
      });
}