# ----------------------------------------------------------------
# The workbench: everything resident inside a bench.
#
# A definition module like ./ree-executor.nix, not a flake package. It
# answers "what is a workbench" once — the outbound listener, the REE
# executor it spawns, and the handler tools those shell out to — and each
# consumer packages a slice of it:
#   ./provider-image.nix  embeds the manifests plus `store-paths` lists that
#                         reference the image's own /nix/store, for injection
#                         into an allocated bench
#   ./exec-bundle.nix     materializes a `store/` copy for hosts that
#                         provision by hand
# Sharing one definition is the point: before this module both of those
# assembled the same closure and rebuilt the same combined manifest
# independently, under different derivation names, from the same inputs.
#
# The provider is *not* part of a workbench. It consumes this module to
# inject it and ships its own process, interpreter and docker client
# separately — "provider never executes" is an import contract, and the
# packaging follows it.
#
# Two manifests, not one. ./tools.nix keeps the tool closure deliberately
# separate from the executor's: the executor is the protocol-coupled
# reproducibility surface and stays minimal, while tools release on their
# own cadence. One delivery artifact does not have to mean one manifest, so
# both are exposed side by side rather than fused.
# ----------------------------------------------------------------
{
  pkgs,
  buildRevision ? "development",
}:

let
  executor = import ./ree-executor.nix { inherit pkgs buildRevision; };
  service = import ./workbench-service.nix { inherit pkgs buildRevision; };
  tools = import ./tools.nix { inherit pkgs; };

  # The executor manifest with the resident listener's path folded in. Every
  # consumer needs exactly this file, so it is built here once.
  execManifest =
    pkgs.runCommand "repo2ree-workbench-manifest.json" { nativeBuildInputs = [ pkgs.jq ]; }
      ''
        jq \
          --arg workbenchPath "${service.bin}/bin/repo2ree-workbench" \
          '. + {workbench_path: $workbenchPath}' \
          ${executor.manifest} > $out
      '';

  # Everything a bench needs present at runtime to execute an REE: the
  # listener, the executor, and the static `sleep` behind the keep-alive
  # command. Consumers either copy these paths or reference them.
  execClosure = pkgs.closureInfo {
    rootPaths = [
      executor.bin
      executor.pause
      service.bin
    ];
  };

  # Every path a self-managed install needs on disk: the exec closure plus the
  # tools. One closureInfo over both root sets rather than two lists, so the
  # paths they share are carried once.
  fullClosure = pkgs.closureInfo {
    rootPaths = [
      executor.bin
      executor.pause
      service.bin
      tools.binDir
      pkgs.cacert
    ];
  };

  # The environment that makes an unpacked workbench usable: where the
  # executor is, where its tools are, and the CA roots the tools need on
  # images that ship no store of their own. The provider sets the same set on
  # a bench it allocates; an image that bakes them in needs no provider.
  toolEnv = {
    REPO2REE_EXEC_PATH = "${executor.bin}/bin/repo2ree-exec";
    REPO2REE_TOOLS_BIN = "${tools.binDir}/bin";
  }
  // tools.extraEnv
  // pkgs.lib.mapAttrs' (
    name: path:
    pkgs.lib.nameValuePair "REPO2REE_TOOL_${pkgs.lib.toUpper (builtins.replaceStrings [ "-" ] [ "_" ] name)}" path
  ) tools.bins;
in
{
  inherit
    executor
    service
    tools
    execManifest
    execClosure
    fullClosure
    toolEnv
    ;

  # The two manifests plus their store-path lists, at the layout the provider
  # reads them from. A consumer that already carries the closure in its own
  # /nix/store references it through these instead of copying it a second time.
  bundleRefDir = pkgs.runCommand "repo2ree-bundles-ref" { } ''
    mkdir -p $out/opt/repo2ree/exec-bundle $out/opt/repo2ree/tools-bundle
    cp ${execManifest} $out/opt/repo2ree/exec-bundle/manifest.json
    cp ${execClosure}/store-paths $out/opt/repo2ree/exec-bundle/store-paths
    cp ${tools.manifest} $out/opt/repo2ree/tools-bundle/manifest.json
    cp ${tools.closure}/store-paths $out/opt/repo2ree/tools-bundle/store-paths
  '';
}
