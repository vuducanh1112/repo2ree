# A machine: a normal distribution with the workbench closure beside it in /nix/store.
{
  pkgs,
  buildRevision,
}:

let
  workbench = import ../../nix/workbench.nix { inherit pkgs buildRevision; };

  # The same pin as the workbench image's base and the images the testbed pins (store_images.py).
  debianWithPython = import ../../nix/debian-with-python.nix { inherit pkgs; };

  # What every machine that starts as root does first: it knows the user the testbed runs as, and
  # `run_as` drops to that user, as whoever logs in to the machine is not root.
  prologue = ''
    #!${pkgs.bash}/bin/bash
    set -euo pipefail
    uid=''${REPO2REE_ENVIRONMENT_USER%:*}
    gid=''${REPO2REE_ENVIRONMENT_USER#*:}
    echo "researcher:x:$uid:$gid::/home/researcher:/bin/sh" >> /etc/passwd
    echo "researcher:x:$gid:" >> /etc/group
    install -d -o "$uid" -g "$gid" /home/researcher
    run_as=(${pkgs.util-linux}/bin/setpriv --reuid="$uid" --regid="$gid" --clear-groups env HOME=/home/researcher)
  '';
in
{
  name,
  packages ? [ ],
  # A script to start the machine's services as root, ending by running its arguments as the user.
  entrypoint ? null,
  variables ? { },
}:
pkgs.dockerTools.buildLayeredImage {
  name = "repo2ree-environment-${name}";
  tag = "local";
  fromImage = debianWithPython;
  config = {
    Entrypoint =
      if entrypoint == null then
        [ ]
      else
        [ "${pkgs.writeScript "entrypoint" (prologue + builtins.readFile entrypoint)}" ];
    Cmd = [ "${workbench.service.bin}/bin/repo2ree-workbench" ];
    Env = [
      "PATH=${
        pkgs.lib.makeBinPath (
          [
            workbench.service.bin
            workbench.executor.bin
          ]
          ++ packages
        )
      }:/usr/local/bin:/usr/bin:/bin"
      "HOME=/tmp"
      "PYTHONUNBUFFERED=1"
    ]
    ++ pkgs.lib.mapAttrsToList (variable: value: "${variable}=${value}") (
      workbench.toolEnv // variables
    );
  };
}
