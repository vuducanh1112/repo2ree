# A machine with a Docker daemon of its own: an REE's scripts run in containers from its image.
{ machine, pkgs }:
machine {
  name = "docker";
  packages = [
    pkgs.docker
    pkgs.iptables
    pkgs.procps
  ];
  entrypoint = ./entrypoint.sh;
}
