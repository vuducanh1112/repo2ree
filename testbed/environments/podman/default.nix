# A machine with rootless Podman and no daemon. On `podman` the workbench runs an REE's scripts in
# containers from its image; on `podman-host` it runs them on the machine, where they call Podman.
{
  machine,
  pkgs,
  name ? "podman",
}:
machine {
  inherit name;
  packages = [ pkgs.podman ];
  entrypoint = ./entrypoint.sh;
  variables = {
    REPO2REE_ENVIRONMENT_FILES = "${./containers}";
    REPO2REE_ENVIRONMENT_SHADOW = "${pkgs.shadow}";
  };
}
