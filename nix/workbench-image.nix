# ----------------------------------------------------------------
# Workbench image — a store's workbench, run beside a host's container engine.
#
# The listener serves one store (--store ID=PATH); ree runs each REE's scripts
# in this container: Debian with Python (debian-with-python.nix), the workbench,
# the executor and the handler tools beside it in /nix/store, and a Docker CLI.
# An REE whose scripts build images reaches the host engine through its socket
# mounted into this container. Whatever else the REEs' checks ask for is the
# deployer's to add, in an image built from this one.
#
#   docker run -v /var/run/docker.sock:/var/run/docker.sock \
#     -v /srv/rees:/srv/rees repo2ree-workbench \
#     repo2ree-workbench --store lab=/srv/rees --connect wss://… --token-file /run/token

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
  debianWithPython = import ./debian-with-python.nix { inherit pkgs; };
in
pkgs.dockerTools.buildLayeredImage {
  name = "repo2ree-workbench";
  # "local" marks never-pushed local builds; published channels (edge, commit
  # shas) are minted at push time by the publishing recipes.
  tag = "local";
  fromImage = debianWithPython;

  contents = [ workbench.bundleRefDir ];

  config = {
    Labels = {
      "org.opencontainers.image.revision" = buildRevision;
    };
    Cmd = [ "${workbench.service.bin}/bin/repo2ree-workbench" ];
    Env = [
      "PATH=${
        pkgs.lib.makeBinPath [
          workbench.service.bin
          workbench.executor.bin
          workbench.tools.binDir
          pkgs.docker-client
          (import ./busybox-command.nix { inherit pkgs; })
        ]
      }:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"
      "WORKBENCH_STATE_DIR=/var/lib/repo2ree-workbench"
      "PYTHONDONTWRITEBYTECODE=1"
      "PYTHONUNBUFFERED=1"
      "REPO2REE_CLI_BUNDLE=/opt/repo2ree/cli-bundle"
      "REPO2REE_TOOLS_BUNDLE=/opt/repo2ree/tools-bundle"
    ]
    ++ pkgs.lib.mapAttrsToList (name: value: "${name}=${value}") workbench.toolEnv;
  };
}
