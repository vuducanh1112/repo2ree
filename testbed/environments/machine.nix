# A machine: a normal distribution with the workbench closure beside it in /nix/store.
#
# Not a Nix image: a machine has /usr/bin/env, a dynamic loader and its own Python, and an
# author's scripts rely on them.
{
  pkgs,
  buildRevision,
}:

let
  workbench = import ../../nix/workbench.nix { inherit pkgs buildRevision; };

  # The digest names every platform; the image differs by architecture, so its hash does too.
  platforms = {
    aarch64-linux = {
      arch = "arm64";
      hash = "sha256-9eUhxerUTE3ALtacyb3Ps9uDCoIjs4a1LFo4mALdcLw=";
    };
    x86_64-linux = {
      arch = "amd64";
      hash = "sha256-urZhYUdNm81I3wpwdEbKwBoLvEf59TBc/m+HKwWDH+g=";
    };
  };
  platform = platforms.${pkgs.stdenv.hostPlatform.system};

  # Debian with Python, the same pin as the images a store offers (store_images.py).
  debianWithPython = pkgs.dockerTools.pullImage {
    imageName = "python";
    imageDigest = "sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534";
    inherit (platform) arch hash;
    os = "linux";
    finalImageName = "python";
    finalImageTag = "3.11-slim";
  };

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
