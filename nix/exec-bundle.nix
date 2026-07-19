# ----------------------------------------------------------------
# The executor bundle: the `repo2ree-exec` closure as a mountable tree.
#
# The agent copies `store/` into a content-addressed docker volume and
# mounts it read-only at /nix/store inside any bench container. Every
# path the wrapper script touches is absolute into that mount, so the
# executor runs in any userland — musl, distroless, whatever the env
# image provides — without relocation or an install step.
#
# `manifest.json` tells the agent the absolute in-container paths, so
# provisioning never assumes anything about the env image's PATH:
#   exec_path  — the repo2ree-exec entrypoint to `docker exec`
#   pause_path — a static `sleep` for the bench keep-alive command,
#                so the env image needs no coreutils of its own
#
# This standalone form carries the closure as a `store/` copy for hosts
# without a nix store. The agent image instead ships manifest.json plus
# a `store-paths` list referencing its own /nix/store (see
# agent-image.nix) — same manifest, no duplicated closure.
#
# Build with:   nix build .#exec-bundle
# Smoke-test:   docker run --rm -v "$(readlink -f result)/store:/nix/store:ro" \
#                 alpine "$(jq -r .exec_path result/manifest.json)" --help
# ----------------------------------------------------------------
{ pkgs }:

let
  executor = import ./ree-executor.nix { inherit pkgs; };
in
pkgs.runCommand "repo2ree-exec-bundle" { } ''
  mkdir -p $out/store
  while IFS= read -r path; do
    cp -a "$path" $out/store/
  done < ${executor.closure}/store-paths

  cp ${executor.manifest} $out/manifest.json
''
