# A one-node Slurm cluster: the workbench on the node, and `srun` able to run jobs there.
{ machine, pkgs }:
machine {
  name = "slurm";
  packages = [
    pkgs.slurm
    pkgs.munge
  ];
  entrypoint = ./entrypoint.sh;
  variables.SLURM_CONF = "${./conf}/slurm.conf";
}
