# ----------------------------------------------------------------
# Workbench bundle — the self-managed install for a host with no nix.
#
# A workbench is an addition to an environment, never an environment itself:
# build scripts run as native subprocesses in the bench, so the host supplies
# the project's toolchain (docker, compilers, language runtimes) and this
# supplies the listener, the REE executor, and the handler tools. That is why
# the delivery form here is a tree you unpack onto a machine you already have,
# rather than a container image that would claim to be the whole environment.
#
#   store/                     every path the closure needs
#   exec-bundle/manifest.json  exec_path, pause_path, workbench_path
#   tools-bundle/manifest.json tool paths, bin_dir, CA env
#   activate                   exports the environment and execs the listener
#
# On a host that already has nix, prefer `nix run .#workbench` — it dedups
# against the existing store instead of unpacking a second copy of CPython.
#
#   RELOCATION: every path in both manifests is absolute into /nix/store,
#   because that is what lets the executor run in any userland without an
#   install step. So `store/` has to *be* /nix/store — bind-mount it there,
#   or use nix-user-chroot / Apptainer on a host where you cannot write it.
#   Unpacking somewhere else and running `activate` will not work, and
#   `activate` says so rather than failing further in.
#
# Build with:   nix build .#workbench-bundle
# Run with:     /nix/store must hold store/, then
#                 ./activate --connect wss://…/workbench/connect --token "$TOKEN"
# ----------------------------------------------------------------
{ pkgs }:

let
  workbench = import ./workbench.nix { inherit pkgs; };

  workbenchPath = "${workbench.service.bin}/bin/repo2ree-workbench";

  exports = pkgs.lib.concatStringsSep "\n" (
    pkgs.lib.mapAttrsToList (
      name: value: "export ${name}=${pkgs.lib.escapeShellArg value}"
    ) workbench.toolEnv
  );

  # POSIX sh, not bash: the point of this form is a host we assume nothing
  # about. The guard is the whole reason this is a generated script and not a
  # line in a README — an unpacked-elsewhere bundle otherwise fails deep inside
  # the first executor spawn with a confusing ENOENT.
  activate = pkgs.writeTextFile {
    name = "repo2ree-workbench-activate";
    executable = true;
    text = ''
      #!/bin/sh
      set -eu

      if [ ! -x ${pkgs.lib.escapeShellArg workbenchPath} ]; then
        echo "repo2ree: ${workbenchPath} is missing." >&2
        echo "The bundle's store/ must be mounted at /nix/store — every path in" >&2
        echo "the manifests is absolute into it. Bind-mount store/ there, then" >&2
        echo "run this again." >&2
        exit 1
      fi

      # An external workbench is one this control plane did not provision; it
      # authenticates with the shared secret in WORKBENCH_AUTH_TOKEN.
      : "''${WORKBENCH_MODE:=external}"
      export WORKBENCH_MODE

      ${exports}

      exec ${workbenchPath} "$@"
    '';
  };
in
pkgs.runCommand "repo2ree-workbench-bundle" { } ''
  mkdir -p $out/store $out/exec-bundle $out/tools-bundle
  while IFS= read -r path; do
    cp -a "$path" $out/store/
  done < ${workbench.fullClosure}/store-paths

  cp ${workbench.execManifest} $out/exec-bundle/manifest.json
  cp ${workbench.tools.manifest} $out/tools-bundle/manifest.json
  cp ${activate} $out/activate
''
