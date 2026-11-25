# ----------------------------------------------------------------
# ree as one file, for a Linux host with no nix.
#
# The executor and its handler tools are the same closure every other
# delivery form carries (ree-cli.nix, tools.nix, through workbench.nix's
# toolEnv), so the executor stays the pinned one. The file is a POSIX sh
# header with a gzip tarball of that closure behind it:
#
#   - the first run unpacks it once, atomically, into
#     ${XDG_CACHE_HOME:-~/.cache}/repo2ree/ree-<digest>/;
#   - every run executes the closure through a static nix-user-chroot, which
#     mounts the unpacked nix/ at /nix in a user namespace of its own. The
#     host's other directories stay where they are, so the REE's scripts run
#     with the host's toolchain and the host's paths, and a Docker daemon sees
#     the paths ree hands it.
#
# It needs unprivileged user namespaces. It hides a host's own /nix from ree
# and the scripts it runs: on a host with nix, run ree from nix instead.
#
# Build with:   nix build .#ree-standalone
# Run with:     ./ree --help
# ----------------------------------------------------------------
{
  pkgs,
  buildRevision ? "development",
}:
let
  workbench = import ./workbench.nix { inherit pkgs buildRevision; };
  exports = pkgs.lib.concatStringsSep "\n" (
    pkgs.lib.mapAttrsToList (
      name: value: "export ${name}=${pkgs.lib.escapeShellArg value}"
    ) workbench.toolEnv
  );
  launcher = pkgs.writeShellScriptBin "ree" ''
    ${exports}
    exec ${workbench.executor.bin}/bin/ree "$@"
  '';
  # Its own tests chroot into a user namespace, which a build sandbox in a
  # container does not grant; the binary is the same either way.
  chroot = pkgs.pkgsStatic.nix-user-chroot.overrideAttrs { doCheck = false; };
  closure = pkgs.closureInfo {
    rootPaths = [
      launcher
      chroot
    ];
  };
  # The payload's offset is a fixed-width number in the header itself, so
  # the header's length does not depend on it.
  header = pkgs.writeText "ree-standalone-header.sh" ''
    #!/bin/sh
    set -eu
    digest=@digest@
    offset=@offset@
    cache="''${XDG_CACHE_HOME:-$HOME/.cache}/repo2ree/ree-$digest"
    if [ ! -x "$cache/nix-user-chroot" ]; then
      mkdir -p "$(dirname "$cache")"
      partial=$(mktemp -d "$cache.partial.XXXXXX")
      trap 'rm -rf "$partial"' EXIT HUP INT TERM
      tail -c "+$offset" "$0" | tar -xzf - -C "$partial"
      ln -s "nix/store/${baseNameOf chroot}/bin/nix-user-chroot" "$partial/nix-user-chroot"
      if ! mv -T "$partial" "$cache" 2>/dev/null; then
        [ -x "$cache/nix-user-chroot" ] || { echo "ree: could not unpack into $cache" >&2; exit 1; }
      fi
      trap - EXIT HUP INT TERM
    fi
    exec "$cache/nix-user-chroot" "$cache/nix" ${launcher}/bin/ree "$@"
    exit 1
  '';
in
pkgs.runCommand "ree-standalone"
  {
    nativeBuildInputs = [
      pkgs.gnutar
      pkgs.gzip
    ];
  }
  ''
    sed 's|^/||' ${closure}/store-paths > paths
    tar --create --sort=name --owner=0 --group=0 --numeric-owner --mtime=@1 \
      --hard-dereference -C / --files-from=paths | gzip -9n > payload.tar.gz
    digest=$(sha256sum payload.tar.gz | cut -c1-16)
    sed "s|@digest@|$digest|" ${header} > head.sh
    # The header holds its own length: ten digits, whatever they say.
    size=$(( $(sed 's|@offset@|0000000000|' head.sh | wc -c) + 1 ))
    sed "s|@offset@|$(printf '%010d' "$size")|" head.sh > header.sh
    mkdir -p $out/bin
    cat header.sh payload.tar.gz > $out/bin/ree
    chmod +x $out/bin/ree
  ''
