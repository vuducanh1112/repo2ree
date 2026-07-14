# ----------------------------------------------------------------
# The REE executor closure: `repo2ree-exec` and everything it reaches.
#
# A definition module, not a flake package — it answers "what is the
# executor" once, and each consumer packages a slice of it:
# nix/agent-image.nix references closure+manifest from the image's own
# /nix/store, and nix/exec-bundle.nix copies the closure into a
# standalone mountable tree. Sharing one definition is the point: every
# delivery form of the executor is the same derivation.
#
# This is a reproducibility-sensitive surface — every REE executes
# through it. Keep the dependency list minimal.
# ----------------------------------------------------------------
{ pkgs }:

let
  # Python runtime carrying only what `repo2ree_executor.cli` reaches at
  # import time. Keep this list minimal — adding deps here grows the
  # closure and bypasses the reproducibility surface we're trying to
  # keep small.
  #
  # The opentelemetry trio backs the executor's span relay: spans are
  # encoded (proto-common) and streamed over stderr for the supervisor to
  # forward. The executor never talks to a collector itself, so the OTLP
  # HTTP exporter and `requests` are deliberately absent — those stay
  # behind the host-side functions in repo2ree_protocol.tracing.
  python = pkgs.python313.withPackages (
    ps: with ps; [
      click
      pydantic
      pyyaml
      opentelemetry-api
      opentelemetry-sdk
      opentelemetry-exporter-otlp-proto-common
    ]
  );

  # Filter to just the Python sources so unrelated repo files don't
  # invalidate the closure hash on every edit.
  cleanPySrc =
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

  srcs = {
    protocol = cleanPySrc ../protocol/src;
    core = cleanPySrc ../core/src;
    executor = cleanPySrc ../executor/src;
  };

  # `repo2ree-exec` entrypoint script. Adds the source dirs to PYTHONPATH
  # and dispatches through the executor's __main__.
  bin = pkgs.writeShellScriptBin "repo2ree-exec" ''
    export PYTHONPATH="${srcs.protocol}:${srcs.core}:${srcs.executor}''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${python}/bin/python -m repo2ree_executor "$@"
  '';

  # A static `sleep` for the bench keep-alive command, so an env image
  # needs no coreutils of its own to host a workbench.
  pause = pkgs.pkgsStatic.busybox;

  # Everything the injected executor needs at runtime, as a store-path
  # list consumers can copy or reference.
  closure = pkgs.closureInfo {
    rootPaths = [
      bin
      pause
    ];
  };

  # The agent-facing manifest: absolute in-container paths, so
  # provisioning never assumes anything about the env image's PATH.
  manifest = pkgs.runCommand "repo2ree-exec-manifest.json" { nativeBuildInputs = [ pkgs.jq ]; } ''
    jq -n \
      --arg execPath "${bin}/bin/repo2ree-exec" \
      --arg pausePath "${pause}/bin/sleep" \
      '{schemaVersion: 1, execPath: $execPath, pausePath: $pausePath}' \
      > $out
  '';
in
{
  inherit
    python
    srcs
    bin
    pause
    closure
    manifest
    ;
}
