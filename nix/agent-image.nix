# ----------------------------------------------------------------
# Agent image
#
# The workbench agent as a self-carrying OCI image: the agent process
# plus the executor and handler-tools bundles it will inject into bench
# containers. They are embedded at /opt/repo2ree/{exec,tools}-bundle so
# agent, executor and tools always ship — and version — together; there
# is no separately installed executor to skew against.
#
# The agent is outbound-only (dials WORKBENCH_API_WS_URL) and drives
# the host container runtime, so run it with the host docker socket:
#
#   docker run -d \
#     -v /var/run/docker.sock:/var/run/docker.sock \
#     -v repo2ree-agent-state:/var/lib/repo2ree-agent \
#     -e WORKBENCH_API_WS_URL=wss://…/agent/connect \
#     repo2ree-agent
#
# The state volume keeps the agent id stable across container
# replacements; without it the id — and the reachability of the REEs
# pinned to it — resets (see repo2ree_agent.__main__).
#
# Build with:   nix build .#agent-image
# Load with:    docker load < result
# ----------------------------------------------------------------
{ pkgs }:

let
  executor = import ./ree-executor.nix { inherit pkgs; };
  tools = import ./tools.nix { inherit pkgs; };

  # The agent's python env: anyio + websockets for the control link,
  # pydantic for the repo2ree_protocol frame models, and the otel trio
  # that repo2ree_protocol.tracing reaches at import time (the package
  # __init__ pulls it in via .log). The OTLP HTTP exporter backs the
  # agent's own trace/metric export when OTLP_ENDPOINT is set (executor
  # spans still relay through the backend without it). The agent
  # deliberately depends only on repo2ree_protocol — it is a frame
  # ferry, not an executor — so core's import graph stays out of this
  # image.
  agentPython = pkgs.python313.withPackages (
    ps: with ps; [
      anyio
      pydantic
      websockets
      opentelemetry-api
      opentelemetry-sdk
      opentelemetry-exporter-otlp-proto-common
      opentelemetry-exporter-otlp-proto-http
    ]
  );

  srcs = {
    inherit (executor.srcs) protocol;
    agent = pkgs.lib.cleanSourceWith {
      src = ../agent/src;
      filter =
        path: type:
        let
          base = baseNameOf path;
        in
        !(type == "directory" && (base == "__pycache__" || base == ".pytest_cache"))
        && !(pkgs.lib.hasSuffix ".pyc" base);
    };
  };

  agentBin = pkgs.writeShellScriptBin "repo2ree-agent" ''
    export PYTHONPATH="${srcs.protocol}:${srcs.agent}''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${agentPython}/bin/python -m repo2ree_agent "$@"
  '';

  # The executor bundle at a fixed path the agent code can find. Unlike
  # the standalone .#exec-bundle (which carries a `store/` copy of the
  # closure for hosts without one), the image already ships the closure
  # in its own /nix/store — the string references in manifest.json and
  # store-paths are what pull it into the layers — so the bundle dir here
  # is just those two files, not a second copy of the closure.
  bundleDir = pkgs.runCommand "repo2ree-bundles-ref" { } ''
    mkdir -p $out/opt/repo2ree/exec-bundle $out/opt/repo2ree/tools-bundle
    cp ${executor.manifest} $out/opt/repo2ree/exec-bundle/manifest.json
    cp ${executor.closure}/store-paths $out/opt/repo2ree/exec-bundle/store-paths
    cp ${tools.manifest} $out/opt/repo2ree/tools-bundle/manifest.json
    cp ${tools.closure}/store-paths $out/opt/repo2ree/tools-bundle/store-paths
  '';
in
pkgs.dockerTools.buildLayeredImage {
  name = "repo2ree-agent";
  # "local" marks never-pushed workbench builds; published channels (edge,
  # commit shas) are minted at push time in the Makefile.
  tag = "local";

  contents = [
    agentBin
    bundleDir

    # The docker runtime shells out to the docker CLI against the
    # mounted host socket; the daemon itself stays on the host, so the
    # client alone suffices.
    pkgs.docker-client

    # Minimal userland for debugging a running agent container.
    pkgs.coreutils
    pkgs.bash

    # TLS roots for the outbound wss:// control link.
    pkgs.cacert
  ];

  config = {
    Entrypoint = [ "${agentBin}/bin/repo2ree-agent" ];
    Env = [
      "PATH=/bin"
      "WORKBENCH_AGENT_STATE_DIR=/var/lib/repo2ree-agent"
      "REPO2REE_EXEC_BUNDLE=/opt/repo2ree/exec-bundle"
      "REPO2REE_TOOLS_BUNDLE=/opt/repo2ree/tools-bundle"
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
      "PYTHONDONTWRITEBYTECODE=1"
      "PYTHONUNBUFFERED=1"
    ];
  };
}
