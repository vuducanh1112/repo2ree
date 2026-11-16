# The machines the environments tier installs a workbench on, each an image to `docker load`.
{
  pkgs,
  buildRevision ? "development",
}:

let
  machine = import ./machine.nix { inherit pkgs buildRevision; };
in
{
  bare = import ./bare { inherit machine; };
  docker = import ./docker { inherit machine pkgs; };
  podman = import ./podman { inherit machine pkgs; };
  slurm = import ./slurm { inherit machine pkgs; };
}
