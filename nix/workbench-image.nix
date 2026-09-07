# ----------------------------------------------------------------
# Workbench image — a transport for the closure, not a runnable bench.
#
# The provider pulls this and populates the shared store volume from its
# /nix/store, then mounts that volume into a bench built from the *user's*
# base image:
#
#   docker run --rm -v repo2ree-store-<digest>:/bundle-store \
#     repo2ree-workbench@sha256:… cp -a /nix/store/. /bundle-store/
#
# Publishing the closure this way lets a provider fetch the runtime by digest
# instead of carrying it inside its own image, and makes the digest recorded
# in the audit trail the digest that actually executed.
#
# Do NOT treat this as a bench you can run on its own. A workbench is an
# *addition* to an environment, never an environment: build scripts run as
# native subprocesses in the bench (see repo2ree_core.execution.process), so
# the bench must carry the project's toolchain. This image carries `sh` and
# the handler tools and nothing else — no docker, no compiler, no language
# runtime — which is why the base image is the user's choice and this is only
# ever injected into it. `doctor` on a bench with just this reports docker
# unavailable, and any REE that builds a container fails.
#
# `Cmd` still names the listener so the image is usable as a base to derive
# from (`FROM repo2ree-workbench`, add your toolchain) — and, being Cmd rather
# than Entrypoint, so the copy above stays a plain `docker run` with no
# --entrypoint flag to lose. `cp` is the static busybox already in the closure
# as the keep-alive `sleep`, so it costs this image nothing.
#
# For a self-managed install on a host that already has its toolchain, use
# .#workbench (nix hosts) or .#workbench-bundle (everything else) — both add
# the workbench to an environment instead of pretending to be one.
#
# Build with:   nix build .#workbench-image
# Load with:    docker load < result
# ----------------------------------------------------------------
{
  pkgs,
  buildRevision ? "development",
}:

let
  workbench = import ./workbench.nix { inherit pkgs buildRevision; };
in
pkgs.dockerTools.buildLayeredImage {
  name = "repo2ree-workbench";
  # "local" marks never-pushed local builds; published channels (edge, commit
  # shas) are minted at push time by the publishing recipes.
  tag = "local";

  contents = [
    workbench.service.bin
    workbench.executor.bin
    # Both the bench keep-alive `sleep` and the `cp` the copy use above; it is
    # static, so it runs in this image and in any bench the closure lands in.
    workbench.executor.pause
    workbench.tools.binDir
    workbench.bundleRefDir

    # TLS roots for the outbound wss:// control link.
    pkgs.cacert
  ];

  # The default root the listener binds. It must exist and be empty: an
  # external workbench refuses to bind onto a non-empty root, which is what
  # stops two allocations from sharing one tree.
  extraCommands = "mkdir -p ree";

  config = {
    Labels = {
      "org.opencontainers.image.revision" = buildRevision;
    };
    Cmd = [ "${workbench.service.bin}/bin/repo2ree-workbench" ];
    Env = [
      "PATH=/bin"
      "WORKBENCH_ROOT=/ree"
      "WORKBENCH_MODE=external"
      "PYTHONDONTWRITEBYTECODE=1"
      "PYTHONUNBUFFERED=1"
      "REPO2REE_EXEC_BUNDLE=/opt/repo2ree/exec-bundle"
      "REPO2REE_TOOLS_BUNDLE=/opt/repo2ree/tools-bundle"
    ]
    ++ pkgs.lib.mapAttrsToList (name: value: "${name}=${value}") workbench.toolEnv;
  };
}
