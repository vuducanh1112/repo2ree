# A one-node Slurm cluster: the workbench on the node, `srun` able to run jobs there, and Apptainer for them to enter.
{ machine, pkgs }:
machine {
  name = "slurm";
  packages = [
    pkgs.slurm
    pkgs.munge
    pkgs.apptainer
  ];
  entrypoint = ./entrypoint.sh;
  variables.SLURM_CONF = "${./conf}/slurm.conf";
}
