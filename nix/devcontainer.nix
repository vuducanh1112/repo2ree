# What the dev container's entrypoint, login shell, and VS Code's server need beyond
# its Debian base and Nix (docker/dev/nix.Dockerfile): dropping to the user, direnv,
# and ps, which VS Code's server runs. From the dev pin, like the dev shell: it ships
# nothing.
{ devPkgs }:
devPkgs.buildEnv {
  name = "repo2ree-devcontainer";
  paths = with devPkgs; [
    direnv
    gosu
    procps
  ];
}
