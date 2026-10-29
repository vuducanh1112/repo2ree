{ pkgs, name }:

let
  inherit (pkgs) lib;
  python = pkgs.python313;
  cleanPySrc = import ./clean-py-src.nix { inherit pkgs; };
  closure = (lib.importJSON ./closures.json).closures.${name};
  system = pkgs.stdenv.hostPlatform.system;

  wheel =
    entry:
    python.pkgs.buildPythonPackage {
      pname = entry.name;
      inherit (entry) version;
      format = "wheel";
      src = pkgs.fetchurl { inherit (entry) url sha256; };
      nativeBuildInputs = lib.optional entry.binary pkgs.autoPatchelfHook;
      buildInputs = lib.optional entry.binary pkgs.stdenv.cc.cc.lib;
      dontCheckRuntimeDeps = true;
      doCheck = false;
    };

  member =
    entry:
    python.pkgs.buildPythonPackage {
      pname = entry.name;
      inherit (entry) version;
      pyproject = true;
      src = cleanPySrc (../. + "/${entry.path}");
      build-system = [ python.pkgs.hatchling ];
      dontCheckRuntimeDeps = true;
      doCheck = false;
    };

  env = python.withPackages (_: map wheel closure.systems.${system} ++ map member closure.workspace);

  modules = lib.concatMap (entry: entry.modules) closure.workspace;

  expected = pkgs.writeText "repo2ree-${name}-closure.json" (
    builtins.toJSON (
      lib.listToAttrs (
        map (entry: lib.nameValuePair entry.name entry.version) (
          closure.systems.${system} ++ closure.workspace
        )
      )
    )
  );

  importEveryModule = pkgs.writeText "import-every-module.py" ''
    import importlib
    import importlib.metadata
    import json
    import pkgutil
    import re
    import sys

    expected = json.load(open(sys.argv[1]))
    installed = {
        re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower(): dist.version
        for dist in importlib.metadata.distributions()
    }
    if installed != expected:
        missing = sorted(set(expected) - set(installed))
        extra = sorted(set(installed) - set(expected))
        differ = sorted(n for n in set(expected) & set(installed) if expected[n] != installed[n])
        sys.exit(f"closure differs from uv.lock: missing={missing} extra={extra} versions={differ}")
    for root in sys.argv[2:]:
        package = importlib.import_module(root)
        for module in pkgutil.walk_packages(package.__path__, f"{root}."):
            if not module.name.endswith(".__main__"):
                importlib.import_module(module.name)
        print(root)
  '';

  imports = pkgs.runCommand "repo2ree-${name}-closure-imports" { } ''
    ${env}/bin/python -I ${importEveryModule} ${expected} ${lib.escapeShellArgs modules} > $out
  '';
in
{
  inherit env imports;
}
