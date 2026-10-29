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

  imports = pkgs.runCommand "repo2ree-${name}-closure-imports" { } ''
    ${env}/bin/python -I ${./import-modules.py} --expect ${expected} ${lib.escapeShellArgs modules} > $out
  '';
in
{
  inherit env imports;
}
