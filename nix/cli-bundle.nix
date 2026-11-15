# ----------------------------------------------------------------
# The executor bundle: the `ree` closure as a mountable tree.
#
# The provider copies `store/` into a content-addressed docker volume and
# mounts it read-only at /nix/store inside any bench container. Every
# path the wrapper script touches is absolute into that mount, so the
# executor runs in any userland — musl, distroless, whatever the env
# image provides — without relocation or an install step.
#
# `manifest.json` tells the provider the absolute in-container paths, so
# provisioning never assumes anything about the env image's PATH:
#   cli_path  — the ree entrypoint to `docker exec`
#   pause_path — a static `sleep` for the bench keep-alive command,
#                so the env image needs no coreutils of its own
#
# `workbench_path` rides along on the same manifest: the bundle carries
# the resident `repo2ree-workbench` too, so a hand-provisioned bench has
# everything a provider-allocated one gets.
#
# This standalone form carries the closure as a `store/` copy for hosts
# without a nix store. The provider image instead ships manifest.json plus
# a `store-paths` list referencing its own /nix/store (see
# provider-image.nix) — same manifest, no duplicated closure.
#
# Build with:   nix build .#cli-bundle
# Smoke-test:   docker run --rm -v "$(readlink -f result)/store:/nix/store:ro" \
#                 alpine "$(jq -r .cli_path result/manifest.json)" --help
# ----------------------------------------------------------------
{
  pkgs,
  buildRevision ? "development",
}:

let
  workbench = import ./workbench.nix { inherit pkgs buildRevision; };
in
pkgs.runCommand "repo2ree-cli-bundle" { } ''
  mkdir -p $out/store
  while IFS= read -r path; do
    cp -a "$path" $out/store/
  done < ${workbench.cliClosure}/store-paths

  cp ${workbench.cliManifest} $out/manifest.json
''
