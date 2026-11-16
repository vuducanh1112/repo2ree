# Debian with Python, pinned by digest: the base of the workbench image and of the testbed's machines.
#
# A normal distribution, not a Nix image: an author's scripts rely on /usr/bin/env, a dynamic loader,
# python3 with venv, tar and CA roots, and a deployer adds what else the REEs' checks ask for with apt.
{ pkgs }:

let
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
in
pkgs.dockerTools.pullImage {
  imageName = "python";
  imageDigest = "sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534";
  inherit (platform) arch hash;
  os = "linux";
  finalImageName = "python";
  finalImageTag = "3.11-slim";
}
