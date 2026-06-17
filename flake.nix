{
  description = "Fullstack Dev Environment with Node 25, UV, and Kubectl";

  inputs = {
    # Nixpkgs unstable usually carries the latest Node versions
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  # Concerns live here, each in its own module under ./nix:
  #   - devshell.nix        local developer tooling (changes often)
  #   - workbench-image.nix the OCI image every REE ships (reproducibility surface)
  #   - frontend-image.nix  the deployed web bundle behind caddy
  # All build against the single pinned nixpkgs below, so the images and
  # the dev env can never drift onto different package revisions.
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          #config.allowUnfree = true; # Needed for some kubectl plugins/drivers
        };

        workbenchImage = import ./nix/workbench-image.nix { inherit pkgs; };

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

        packages = {
          workbench-image = workbenchImage;
          frontend-image = frontendImage;
          default = workbenchImage;
        };
      });
}
