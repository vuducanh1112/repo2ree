# A static busybox as one command, not its applets: whatever needs a root filesystem with no
# libraries (a FROM scratch image) takes it, and it shadows nothing the distribution has.
{ pkgs }:
pkgs.runCommand "busybox-command" { } ''
  mkdir -p $out/bin
  ln -s ${pkgs.pkgsStatic.busybox}/bin/busybox $out/bin/busybox
''
