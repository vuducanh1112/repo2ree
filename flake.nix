{
  description = "Fullstack Dev Environment with Node 25, UV, and Kubectl";

  inputs = {
    # Nixpkgs unstable usually carries the latest Node versions
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  # Two concerns live here, each in its own module under ./nix:
  #   - devshell.nix       local developer tooling (changes often)
  #   - workbench-image.nix the OCI image every REE ships (reproducibility surface)
  # Both build against the single pinned nixpkgs below, so the image and
  # the dev env can never drift onto different package revisions.
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          #config.allowUnfree = true; # Needed for some kubectl plugins/drivers
        };

        workbenchImage = import ./nix/workbench-image.nix { inherit pkgs; };
      in
      {
        devShells.default = import ./nix/devshell.nix { inherit pkgs; };

        packages = {
          workbench-image = workbenchImage;
          default = workbenchImage;
        };
      });
}
