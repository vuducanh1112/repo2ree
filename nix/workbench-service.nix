# ----------------------------------------------------------------
# The workbench service: `repo2ree-workbench` and its interpreter.
#
# A definition module like ./ree-executor.nix, not a flake package. The
# workbench is never shipped as an image of its own: the provider injects
# this closure into each bench it allocates (./provider-image.nix), and
# ./exec-bundle.nix carries it for hosts that provision by hand.
#
# It is deliberately substrate-free — repo2ree_protocol and nothing else,
# no docker, no core, no executor — which is what lets the same binary run
# inside an arbitrary selected environment image.
# ----------------------------------------------------------------
{
  pkgs,
  buildRevision ? "development",
}:

let
  cleanPySrc = import ./clean-py-src.nix { inherit pkgs; };

  # Everything `repo2ree_workbench` reaches at import time: pydantic for the
  # repo2ree_protocol frame models, websockets for the outbound control link,
  # and the otel set that repo2ree_protocol.tracing pulls in via .log. The
  # OTLP HTTP exporter backs the workbench's own trace/metric export when
  # OTLP_ENDPOINT is set (executor spans still relay through the backend
  # without it).
  #
  # Two entries are load-bearing in a way the dependency metadata does not
  # show, each found by a startup crash rather than by reading it:
  #   opentelemetry-instrumentation-logging — protocol/pyproject.toml declares
  #     it and tracing.otlp_log_handler imports from it. Adding it only became
  #     a fix once the nixpkgs bump brought 0.64b0; the 0.55b0 this pin used to
  #     carry has no `handler` submodule at all.
  #   packaging — a runtime import of opentelemetry-instrumentation's _semconv
  #     module that nixpkgs does not propagate, so withPackages leaves it out
  #     and the handler import above dies on `No module named 'packaging'`.
  #     Verified by running the import in this exact env, not inferred.
  #
  # ./provider-image.nix builds the provider's own interpreter by extending
  # this list, so a fix here reaches both processes.
  pythonPackages =
    ps: with ps; [
      pydantic
      websockets
      opentelemetry-api
      opentelemetry-sdk
      opentelemetry-exporter-otlp-proto-common
      opentelemetry-exporter-otlp-proto-http
      opentelemetry-instrumentation-logging
      packaging
    ];

  python = pkgs.python313.withPackages pythonPackages;

  protocolSource = cleanPySrc ../protocol/src;
  workbenchSource = cleanPySrc ../workbench/src;

  bin = pkgs.writeShellScriptBin "repo2ree-workbench" ''
    export REPO2REE_BUILD_REVISION=${pkgs.lib.escapeShellArg buildRevision}
    export PYTHONPATH="${protocolSource}:${workbenchSource}''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${python}/bin/python -m repo2ree_workbench "$@"
  '';
in
{
  inherit
    bin
    python
    pythonPackages
    protocolSource
    workbenchSource
    ;
}
