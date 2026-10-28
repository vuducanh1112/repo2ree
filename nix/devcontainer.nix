# What the dev container's entrypoint and login shell need beyond its Nix base
# image (docker/dev/nix.Dockerfile): dropping to the user, matching the Docker
# socket's group, and direnv. From the dev pin, like the dev shell: it ships nothing.
{ devPkgs }:
devPkgs.buildEnv {
  name = "repo2ree-devcontainer";
  paths = with devPkgs; [
    direnv
    getent
    gnused
    gosu
  ];
}
