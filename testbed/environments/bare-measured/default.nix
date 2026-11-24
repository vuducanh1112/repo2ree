# The bare machine with `ree-measured` beside `ree`: the same executor, its sources and its packages, run under
# coverage.py, so the testbed measures what an exercise executes on a machine of its own. Only the testbed uses it;
# the executor every REE runs through stays as nix/ree-cli.nix builds it.
{
  machine,
  pkgs,
  executor,
  buildRevision,
}:

let
  python = pkgs.python313.withPackages (ps: executor.pythonPackages ps ++ [ ps.coverage ]);

  # What the checkout's pyproject.toml measures of these packages; the data file is the caller's, by COVERAGE_FILE.
  rc = pkgs.writeText "ree-measured.coveragerc" ''
    [run]
    branch = true
    parallel = true
    sigterm = true
    source_pkgs =
        repo2ree_ree
        repo2ree_protocol
        repo2ree_telemetry
        repo2ree_authoring
        repo2ree_core
        repo2ree_cli
    omit =
        */__main__.py
  '';

  measured = pkgs.writeShellScriptBin "ree-measured" ''
    export REPO2REE_BUILD_REVISION=${pkgs.lib.escapeShellArg buildRevision}
    export PYTHONPATH="${pkgs.lib.concatStringsSep ":" executor.pythonPath}''${PYTHONPATH:+:$PYTHONPATH}"
    exec ${python}/bin/python -m coverage run --rcfile=${rc} -m repo2ree_cli "$@"
  '';
in
machine {
  name = "bare-measured";
  packages = [ measured ];
}
