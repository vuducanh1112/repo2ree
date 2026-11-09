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
  # An REE that declares it needs a container engine reaches this machine's daemon.
  variables.WORKBENCH_SCRIPT_ENGINE = "socket";
}
