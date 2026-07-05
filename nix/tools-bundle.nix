# ----------------------------------------------------------------
# The handler-tools closure as a standalone mountable tree — the tools
# counterpart of ./exec-bundle.nix, same layout (`store/` copy +
# `manifest.json`), for hosts without a nix store. The agent image
# instead ships the manifest + store-paths referencing its own
# /nix/store (see agent-image.nix).
#
# Build with:   nix build .#tools-bundle
# ----------------------------------------------------------------
{ pkgs }:

let
  tools = import ./tools.nix { inherit pkgs; };
in
pkgs.runCommand "repo2ree-tools-bundle" { } ''
  mkdir -p $out/store
  while IFS= read -r path; do
    cp -a "$path" $out/store/
  done < ${tools.closure}/store-paths

  cp ${tools.manifest} $out/manifest.json
''
