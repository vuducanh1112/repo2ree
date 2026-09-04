# ----------------------------------------------------------------
# Filter a source tree down to its Python sources.
#
# __pycache__, .pyc and .pytest_cache are local build state, not source.
# Copying them into the store makes a derivation's hash depend on whatever
# the developer last ran, which is exactly what the shipped closures must
# not do. Every module that puts a package's src/ into the store goes
# through this.
# ----------------------------------------------------------------
{ pkgs }:

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
}
