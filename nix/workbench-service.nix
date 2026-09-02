{ pkgs }:

let
  python = pkgs.python313.withPackages (
    ps: with ps; [
      pydantic
      websockets
      opentelemetry-api
      opentelemetry-sdk
      opentelemetry-exporter-otlp-proto-common
      opentelemetry-exporter-otlp-proto-http
      opentelemetry-instrumentation-logging
      packaging
    ]
  );
  cleanSource =
    src:
    pkgs.lib.cleanSourceWith {
      inherit src;
      filter =
        path: type:
        let
          base = baseNameOf path;
        in
        !(type == "directory" && (base == "__pycache__" || base == ".pytest_cache"))
        && !(pkgs.lib.hasSuffix ".pyc" base);
    };
  protocolSource = cleanSource ../protocol/src;
  workbenchSource = cleanSource ../workbench/src;
  bin = pkgs.writeShellScriptBin "repo2ree-workbench" ''
    export PYTHONPATH="${protocolSource}:${workbenchSource}''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${python}/bin/python -m repo2ree_workbench "$@"
  '';
in
{
  inherit bin python protocolSource workbenchSource;
}
