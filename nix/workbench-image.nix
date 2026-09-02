# ----------------------------------------------------------------
# Docker provider image
#
# The provider service as a self-carrying OCI image. It owns the host Docker
# socket and carries the workbench, executor, and handler-tool closures it
# injects into each allocated environment. The resident workbench itself has
# no Docker provisioning dependency.
#
# The workbench is outbound-only (dials WORKBENCH_API_WS_URL) and drives
# the host container runtime, so run it with the host docker socket:
#
#   docker run -d \
#     -v /var/run/docker.sock:/var/run/docker.sock \
#     -v repo2ree-provider-state:/var/lib/repo2ree-provider \
#     -e PROVIDER_API_WS_URL=wss://…/provider/connect \
#     -e PROVIDER_WORKBENCH_API_WS_URL=wss://…/workbench/connect \
#     repo2ree-provider-docker
#
# The state volume keeps the provider identity stable across replacements.
#
# Build with:   nix build .#workbench-image
# Load with:    docker load < result
# ----------------------------------------------------------------
{ pkgs }:

let
  executor = import ./ree-executor.nix { inherit pkgs; };
  tools = import ./tools.nix { inherit pkgs; };
  workbench = import ./workbench-service.nix { inherit pkgs; };

  # Shared Python runtime for the provider and injected workbench.
  # pydantic for the repo2ree_protocol frame models, and the otel trio
  # that repo2ree_protocol.tracing reaches at import time (the package
  # __init__ pulls it in via .log). The OTLP HTTP exporter backs the
  # workbench's own trace/metric export when OTLP_ENDPOINT is set (executor
  # spans still relay through the backend without it). The workbench
  # deliberately depends only on repo2ree_protocol — it is a frame
  # ferry, not an executor — so core's import graph stays out of this
  # image.
  providerPython = pkgs.python313.withPackages (
    ps: with ps; [
      anyio
      pydantic
      websockets
      opentelemetry-api
      opentelemetry-sdk
      opentelemetry-exporter-otlp-proto-common
      opentelemetry-exporter-otlp-proto-http
      # protocol/pyproject.toml declares this too, and tracing.otlp_log_handler
      # imports from it. It was missing here, which crashed every workbench on
      # startup; adding it only became a fix once the nixpkgs bump brought
      # 0.64b0, since the 0.55b0 this pin used to carry has no `handler`
      # submodule at all.
      opentelemetry-instrumentation-logging
      # A runtime import of opentelemetry-instrumentation's _semconv module
      # that nixpkgs does not propagate, so withPackages leaves it out and the
      # handler import above dies on `No module named 'packaging'` — the same
      # startup crash, one layer down. Verified by running the import in this
      # exact env, not inferred from the dependency metadata.
      packaging
    ]
  );

  srcs = {
    inherit (executor.srcs) protocol;
    dockerSupport = pkgs.lib.cleanSource ../docker-support/src;
    provider = pkgs.lib.cleanSource ../provider/src;
  };

  providerBin = pkgs.writeShellScriptBin "repo2ree-provider-docker" ''
    export PYTHONPATH="${srcs.protocol}:${srcs.dockerSupport}:${srcs.provider}''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${providerPython}/bin/python -m repo2ree_provider_docker "$@"
  '';

  # The provider copies this complete closure into a content-addressed Docker
  # volume. That is what makes the same workbench executable available inside
  # arbitrary selected environment images without assuming it is preinstalled.
  injectedClosure = pkgs.closureInfo {
    rootPaths = [
      executor.bin
      executor.pause
      workbench.bin
    ];
  };

  # The executor bundle at a fixed path the workbench code can find. Unlike
  # the standalone .#exec-bundle (which carries a `store/` copy of the
  # closure for hosts without one), the image already ships the closure
  # in its own /nix/store — the string references in manifest.json and
  # store-paths are what pull it into the layers — so the bundle dir here
  # is just those two files, not a second copy of the closure.
  execManifest = pkgs.runCommand "repo2ree-provider-exec-manifest.json" { nativeBuildInputs = [ pkgs.jq ]; } ''
    jq \
      --arg workbenchPath "${workbench.bin}/bin/repo2ree-workbench" \
      '. + {workbench_path: $workbenchPath}' \
      ${executor.manifest} > $out
  '';

  bundleDir = pkgs.runCommand "repo2ree-bundles-ref" { } ''
    mkdir -p $out/opt/repo2ree/exec-bundle $out/opt/repo2ree/tools-bundle
    cp ${execManifest} $out/opt/repo2ree/exec-bundle/manifest.json
    cp ${injectedClosure}/store-paths $out/opt/repo2ree/exec-bundle/store-paths
    cp ${tools.manifest} $out/opt/repo2ree/tools-bundle/manifest.json
    cp ${tools.closure}/store-paths $out/opt/repo2ree/tools-bundle/store-paths
  '';
in
pkgs.dockerTools.buildLayeredImage {
  name = "repo2ree-provider-docker";
  # "local" marks never-pushed workbench builds; published channels (edge,
  # commit shas) are minted at push time by the publishing recipes.
  tag = "local";

  contents = [
    providerBin
    workbench.bin
    bundleDir

    # The docker runtime shells out to the docker CLI against the
    # mounted host socket; the daemon itself stays on the host, so the
    # client alone suffices.
    pkgs.docker-client

    # Minimal userland for debugging a running workbench container.
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
      "REPO2REE_WORKBENCH_PATH=${workbench.bin}/bin/repo2ree-workbench"
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
      "PYTHONDONTWRITEBYTECODE=1"
      "PYTHONUNBUFFERED=1"
    ];
  };
}
