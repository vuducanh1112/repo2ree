# ----------------------------------------------------------------
# Docker provider image
#
# The provider service as a self-carrying OCI image. It owns the host Docker
# socket and carries the workbench, executor, and handler-tool closures it
# injects into each allocated environment. The workbench it starts inside a
# bench has no Docker dependency of its own — that asymmetry is the whole
# point of the split, and this image is where the provider side of it lands.
#
# The provider is outbound-only (it dials PROVIDER_API_WS_URL) and drives the
# host container runtime, so run it with the host docker socket:
#
#   docker run -d \
#     -v /var/run/docker.sock:/var/run/docker.sock \
#     -v repo2ree-provider-state:/var/lib/repo2ree-provider \
#     -e PROVIDER_API_WS_URL=wss://…/provider/connect \
#     -e PROVIDER_WORKBENCH_API_WS_URL=wss://…/workbench/connect \
#     repo2ree-provider-docker
#
# PROVIDER_WORKBENCH_API_WS_URL is never dialled by the provider itself; it is
# handed to each workbench it starts, which dials the control plane on its own
# separate socket.
#
# The state volume keeps the provider identity stable across replacements.
#
# Build with:   nix build .#provider-image
# Load with:    docker load < result
# ----------------------------------------------------------------
{
  pkgs,
  buildRevision ? "development",
}:

let
  workbench = import ./workbench.nix { inherit pkgs buildRevision; };
  provider = import ./python-closure.nix {
    inherit pkgs;
    name = "provider";
  };

  providerBin = pkgs.writeShellScriptBin "repo2ree-provider-docker" ''
    export REPO2REE_BUILD_REVISION=${pkgs.lib.escapeShellArg buildRevision}
    exec ${provider.env}/bin/python -m repo2ree_provider_docker "$@"
  '';

in
pkgs.dockerTools.buildLayeredImage {
  name = "repo2ree-provider-docker";
  # "local" marks never-pushed local builds; published channels (edge,
  # commit shas) are minted at push time by the publishing recipes.
  tag = "local";

  contents = [
    providerBin
    workbench.service.bin
    workbench.bundleRefDir

    # The docker runtime shells out to the docker CLI against the
    # mounted host socket; the daemon itself stays on the host, so the
    # client alone suffices.
    pkgs.docker-client

    # Minimal userland for debugging a running provider container.
    pkgs.coreutils
    pkgs.bash

    # TLS roots for the outbound wss:// control link.
    pkgs.cacert
  ];

  extraCommands = "test -s ${provider.imports}";

  config = {
    Labels = {
      "org.opencontainers.image.revision" = buildRevision;
    };
    Entrypoint = [ "${providerBin}/bin/repo2ree-provider-docker" ];
    Env = [
      "PATH=/bin"
      "PROVIDER_STATE_DIR=/var/lib/repo2ree-provider"
      "REPO2REE_EXEC_BUNDLE=/opt/repo2ree/exec-bundle"
      "REPO2REE_TOOLS_BUNDLE=/opt/repo2ree/tools-bundle"
      "REPO2REE_WORKBENCH_PATH=${workbench.service.bin}/bin/repo2ree-workbench"
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
      "PYTHONDONTWRITEBYTECODE=1"
      "PYTHONUNBUFFERED=1"
    ];
  };
}
