# A machine with rootless Podman and no daemon: an REE's scripts run on it and call Podman themselves.
{ machine, pkgs }:
machine {
  name = "podman";
  packages = [ pkgs.podman ];
  entrypoint = ./entrypoint.sh;
  variables = {
    REPO2REE_ENVIRONMENT_FILES = "${./containers}";
    REPO2REE_ENVIRONMENT_SHADOW = "${pkgs.shadow}";
  };
}
