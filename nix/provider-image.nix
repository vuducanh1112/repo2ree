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
{ pkgs }:

let
  cleanPySrc = import ./clean-py-src.nix { inherit pkgs; };
  workbench = import ./workbench.nix { inherit pkgs; };

  # The provider's own interpreter: the workbench listener's runtime — the two
  # speak the same repo2ree_protocol frames, so they need the same imports —
  # plus anyio for the provider's connection pump. Extending that list rather
  # than restating it keeps a fix to either process from missing the other; see
  # the comments on it in ./workbench-service.nix. Note that the *injected*
  # listener runs on the interpreter from that module, not on this one.
  #
  # The provider deliberately reaches only repo2ree_protocol and
  # repo2ree_docker — it provisions, it never executes — so core's import
  # graph stays out of this image.
  providerPython = pkgs.python313.withPackages (
    ps: workbench.service.pythonPackages ps ++ [ ps.anyio ]
  );

  srcs = {
    inherit (workbench.executor.srcs) protocol;
    dockerSupport = cleanPySrc ../docker-support/src;
    provider = cleanPySrc ../provider/src;
  };

  providerBin = pkgs.writeShellScriptBin "repo2ree-provider-docker" ''
    export PYTHONPATH="${srcs.protocol}:${srcs.dockerSupport}:${srcs.provider}''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${providerPython}/bin/python -m repo2ree_provider_docker "$@"
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

  config = {
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
