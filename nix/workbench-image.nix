# ----------------------------------------------------------------
# Workbench image — a store's workbench, run beside a host's container engine.
#
# The listener serves one store (--store ID=PATH) and runs each REE's scripts
# in a fresh container from the image the REE declares (--backend container),
# started through the host engine's socket mounted into this container. So it
# carries the Docker CLI beside the workbench, the executor and the handler
# tools, and no toolchain of its own: the REE's image is the toolchain.
#
# The store directory must be mounted at the same path it has on the host, so
# a job container the host engine starts sees the REE where the workbench
# does (or pass --engine-path LOCAL=ENGINE).
#
#   docker run -v /var/run/docker.sock:/var/run/docker.sock \
#     -v /srv/rees:/srv/rees repo2ree-workbench \
#     repo2ree-workbench --store lab=/srv/rees --backend container \
#       --script-engine socket --connect wss://… --token-file /run/token
#
# For a host that already has its toolchain and runs scripts on itself, use
# .#workbench (nix hosts) or .#workbench-bundle (everything else).
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
    # A static busybox: the shell and coreutils the handlers' scripts expect.
    workbench.executor.pause
    workbench.tools.binDir
    workbench.bundleRefDir
    # The engine client each REE's job containers are started with, through the host's socket.
    pkgs.docker-client

    # TLS roots for the outbound wss:// control link.
    pkgs.cacert
  ];

  # Scratch space: generated venvs build under /tmp, as on any host.
  extraCommands = "mkdir -p tmp && chmod 1777 tmp";

  config = {
    Labels = {
      "org.opencontainers.image.revision" = buildRevision;
    };
    Cmd = [ "${workbench.service.bin}/bin/repo2ree-workbench" ];
    Env = [
      "PATH=/bin"
      "WORKBENCH_BACKEND=container"
      "WORKBENCH_STATE_DIR=/var/lib/repo2ree-workbench"
      "PYTHONDONTWRITEBYTECODE=1"
      "PYTHONUNBUFFERED=1"
      "REPO2REE_EXEC_BUNDLE=/opt/repo2ree/exec-bundle"
      "REPO2REE_TOOLS_BUNDLE=/opt/repo2ree/tools-bundle"
    ]
    ++ pkgs.lib.mapAttrsToList (name: value: "${name}=${value}") workbench.toolEnv;
  };
}
