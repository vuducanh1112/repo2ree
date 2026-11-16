# A machine with a Docker daemon of its own: an REE's scripts run on it and call Docker themselves.
{ machine, pkgs }:
machine {
  name = "docker";
  packages = [
    pkgs.docker
    pkgs.iptables
    pkgs.procps
    (import ../../../nix/busybox-command.nix { inherit pkgs; })
  ];
  entrypoint = ./entrypoint.sh;
}
