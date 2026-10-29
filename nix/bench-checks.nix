{
  pkgs,
  buildRevision ? "development",
}:

let
  inherit (pkgs) lib;
  workbench = import ./workbench.nix { inherit pkgs buildRevision; };

  closures = {
    executor = {
      inherit (workbench.executor) python pythonPath;
      modules = [
        "repo2ree_ree"
        "repo2ree_protocol"
        "repo2ree_telemetry"
        "repo2ree_authoring"
        "repo2ree_core"
        "repo2ree_executor"
      ];
    };
    workbench = {
      inherit (workbench.service) python pythonPath;
      modules = [
        "repo2ree_ree"
        "repo2ree_protocol"
        "repo2ree_telemetry"
        "repo2ree_workbench"
      ];
    };
  };

  run =
    closure: command:
    "PYTHONPATH=${lib.concatStringsSep ":" closure.pythonPath} ${closure.python}/bin/python ${command}";

  distributions = pkgs.writeText "distributions.py" ''
    import importlib.metadata
    import json

    print(json.dumps({dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()}))
  '';
in
{
  imports = pkgs.runCommand "repo2ree-bench-imports" { } (
    lib.concatMapStrings (closure: ''
      ${run closure "${./import-modules.py} ${lib.escapeShellArgs closure.modules}"} >> $out
    '') (lib.attrValues closures)
  );

  distributions = pkgs.runCommand "repo2ree-bench-distributions" { } ''
    mkdir $out
    ${lib.concatStrings (
      lib.mapAttrsToList (name: closure: ''
        ${run closure "${distributions}"} > $out/${name}.json
      '') closures
    )}
  '';
}
