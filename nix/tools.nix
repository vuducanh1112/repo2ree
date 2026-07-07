# ----------------------------------------------------------------
# Handler tools the agent ships into benches.
#
# A definition module like ./ree-executor.nix, but for the tools core
# handlers and lifecycle scripts shell out to rather than the executor
# itself. Kept as a separate closure on purpose: the executor closure is
# the protocol-coupled reproducibility surface and must stay minimal,
# while tools have their own (faster) release cadence and couple to
# nothing — the manifest records exactly which build produced each
# artifact.
#
# Two consumption forms, both advertised through the manifest:
#   - per-tool absolute paths (``tools``) → REPO2REE_TOOL_<NAME> env,
#     for handlers that resolve explicitly (repo2ree_core.tooling);
#   - a symlink-farm ``binDir`` → prepended to PATH by the *executor*
#     at startup (not by the container env, which would clobber the
#     image's own PATH), so lifecycle scripts calling bare ``git`` /
#     ``curl`` / ``tar`` work on images that ship none of them.
#
# A bench where the agent shipped no tools closure simply reports these
# capabilities as absent; nothing here is required to execute an REE.
# ----------------------------------------------------------------
{ pkgs }:

let
  # Tool name -> package + advertised binary. The name keys become the
  # REPO2REE_TOOL_<NAME> env vars the agent sets on injected benches.
  toolPkgs = {
    # generate-sbom scans the workspace/runtime image natively.
    syft = {
      pkg = pkgs.syft;
      bin = "syft";
    };
    # Source acquisition: acquire_source.sh clones/fetches/extracts.
    # These mirror the reproducer's prerequisites.
    # gitMinimal: no perl/gui/manpage closure — acquisition needs clone/checkout only.
    git = {
      pkg = pkgs.gitMinimal;
      bin = "git";
    };
    curl = {
      pkg = pkgs.curl;
      bin = "curl";
    };
    unzip = {
      pkg = pkgs.unzip;
      bin = "unzip";
    };
    tar = {
      pkg = pkgs.gnutar;
      bin = "tar";
    };
    gzip = {
      pkg = pkgs.gzip;
      bin = "gzip";
    };
  };

  bins = pkgs.lib.mapAttrs (_name: t: "${t.pkg}/bin/${t.bin}") toolPkgs;

  # One PATH entry covering every tool, for the executor to prepend.
  binDir = pkgs.buildEnv {
    name = "repo2ree-tools-bin";
    paths = map (t: t.pkg) (builtins.attrValues toolPkgs);
    pathsToLink = [ "/bin" ];
  };

  caBundle = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
  # Applied verbatim to the bench container env: TLS roots for the
  # https:// paths through git/curl on images that ship no CA store.
  extraEnv = {
    SSL_CERT_FILE = caBundle;
    CURL_CA_BUNDLE = caBundle;
    GIT_SSL_CAINFO = caBundle;
  };

  closure = pkgs.closureInfo {
    rootPaths = [
      binDir
      pkgs.cacert
    ];
  };

  manifest = pkgs.runCommand "repo2ree-tools-manifest.json" { nativeBuildInputs = [ pkgs.jq ]; } ''
    jq -n \
      --argjson tools '${builtins.toJSON bins}' \
      --arg binDir "${binDir}/bin" \
      --argjson env '${builtins.toJSON extraEnv}' \
      '{schemaVersion: 1, tools: $tools, binDir: $binDir, env: $env}' \
      > $out
  '';
in
{
  inherit
    bins
    binDir
    closure
    manifest
    ;
}
