{
  description = "Fullstack Dev Environment with Node 25, UV, and Kubectl";

  inputs = {
    # Nixpkgs unstable usually carries the latest Node versions
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  # Concerns live here, each in its own module under ./nix:
  #   - devshell.nix        local developer tooling (changes often)
  #   - ree-executor.nix    the repo2ree-exec closure (shared, not a package)
  #   - tools.nix           handler-tools closure, e.g. syft (shared, not a package)
  #   - exec-bundle.nix     the executor closure as a mountable tree + manifest
  #   - tools-bundle.nix    the tools closure, same standalone form
  #   - agent-image.nix     the workbench agent + embedded exec/tools bundles
  #                         (the reproducibility surface: every bench executes
  #                         through what it injects)
  #   - frontend-image.nix  the deployed web bundle behind caddy
  # All build against the single pinned nixpkgs below, so the images and
  # the dev env can never drift onto different package revisions.
  outputs =
    {
      nixpkgs,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          #config.allowUnfree = true; # Needed for some kubectl plugins/drivers
        };

        # VITE_API_BASE_URL is baked into the bundle at build time. Empty
        # string => same-origin "/api", which is what the compose setup uses
        # (caddy and the API share an origin via the compose network / proxy).
        # For a non-same-origin backend, set viteApiBaseUrl here.
        frontendImage = import ./nix/frontend-image.nix {
          inherit pkgs;
          viteApiBaseUrl = "";
        };
      in
      {
        devShells.default = import ./nix/devshell.nix { inherit pkgs; };

        formatter = pkgs.nixfmt-tree;

        packages = rec {
          exec-bundle = import ./nix/exec-bundle.nix { inherit pkgs; };
          tools-bundle = import ./nix/tools-bundle.nix { inherit pkgs; };
          agent-image = import ./nix/agent-image.nix { inherit pkgs; };
          frontend-image = frontendImage;
          default = agent-image;
        };
      }
    );
}
