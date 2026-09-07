{
  description = "Fullstack Dev Environment with Node 24, UV, and Kubectl";

  inputs = {
    # Nixpkgs unstable usually carries the latest Node versions
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  # Concerns live here, each in its own module under ./nix:
  #   - devshell.nix          local developer tooling (changes often)
  #   - clean-py-src.nix      the shared "Python sources only" source filter
  #   - ree-executor.nix      the repo2ree-exec closure (shared, not a package)
  #   - workbench-service.nix the repo2ree-workbench listener closure (shared)
  #   - tools.nix             handler-tools closure, e.g. syft (shared, not a package)
  #   - workbench.nix         the three above assembled: what a bench holds.
  #                           Every delivery form derives from this one module
  #   - workbench-image.nix   the workbench closure as an OCI image: transport
  #                           for injection, not a bench (it has no toolchain)
  #   - workbench-bundle.nix  the whole workbench as an unpackable tree, for
  #                           self-managed installs on hosts without nix
  #   - exec-bundle.nix       the executor + workbench closures as a mountable
  #                           tree + manifest
  #   - tools-bundle.nix      the tools closure, same standalone form
  #   - provider-image.nix    the Docker provider service + embedded
  #                           exec/tools bundles (the reproducibility surface:
  #                           every bench executes through what it injects)
  #   - gui-image.nix         the deployed web bundle behind caddy
  # All build against the single pinned nixpkgs below, so the images and
  # the dev env can never drift onto different package revisions.
  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        buildRevision = self.rev or self.dirtyRev or "development";
        pkgs = import nixpkgs {
          inherit system;
          #config.allowUnfree = true; # Needed for some kubectl plugins/drivers
        };

        # VITE_API_BASE_URL is baked into the bundle at build time. Empty
        # string => same-origin "/api", which is what the compose setup uses
        # (caddy and the API share an origin via the compose network / proxy).
        # For a non-same-origin backend, set viteApiBaseUrl here.
        guiImage = import ./nix/gui-image.nix {
          inherit pkgs;
          inherit buildRevision;
          viteApiBaseUrl = "";
        };
      in
      {
        devShells.default = import ./nix/devshell.nix { inherit pkgs; };

        formatter = pkgs.nixfmt-tree;

        packages = rec {
          # The listener on its own, for a host that already has nix and
          # supplies its own isolation: `nix run .#workbench -- --connect …`.
          workbench = (import ./nix/workbench.nix { inherit pkgs buildRevision; }).service.bin;
          # The self-managed install for a host with no nix: closure, both
          # manifests, and a generated `activate`. Tar it to distribute.
          workbench-bundle = import ./nix/workbench-bundle.nix { inherit pkgs buildRevision; };
          exec-bundle = import ./nix/exec-bundle.nix { inherit pkgs buildRevision; };
          tools-bundle = import ./nix/tools-bundle.nix { inherit pkgs; };
          # Transport for the closure the provider copies into its shared
          # store volume — not a bench you can run: it carries no toolchain.
          workbench-image = import ./nix/workbench-image.nix { inherit pkgs buildRevision; };
          provider-image = import ./nix/provider-image.nix { inherit pkgs buildRevision; };
          gui-image = guiImage;
          default = provider-image;
        };
      }
    );
}
