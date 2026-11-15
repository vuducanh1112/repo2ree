#!/usr/bin/env sh
set -eu

# Checks the working environment offers what the REE's scripts need: it runs there, launched as every script is,
# before them, and must exit 0. A reviewer who runs the REE elsewhere learns from it what the scripts expect.
# As it comes it checks nothing and passes. Uncomment and edit the checks that apply; each fails the check with a
# line saying what is missing.

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

# A tool on the PATH.
# command -v git >/dev/null 2>&1 || fail "git is not installed"

# Python, at least a version.
# command -v python3 >/dev/null 2>&1 || fail "python3 is not installed"
# python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || fail "python3 is older than 3.11"

# A Python package, importable.
# python3 -c 'import numpy' 2>/dev/null || fail "numpy is not importable"

# A C compiler.
# command -v cc >/dev/null 2>&1 || fail "no C compiler"

# Java and Maven.
# command -v java >/dev/null 2>&1 || fail "java is not installed"
# command -v mvn >/dev/null 2>&1 || fail "maven is not installed"

# Conda.
# command -v conda >/dev/null 2>&1 || fail "conda is not installed"

# A container engine the scripts can reach (a build that runs docker or podman itself).
# docker info >/dev/null 2>&1 || podman info >/dev/null 2>&1 || fail "no container engine is reachable"

# An NVIDIA GPU, and its driver at least a version.
# command -v nvidia-smi >/dev/null 2>&1 || fail "nvidia-smi is not installed"
# nvidia-smi --query-gpu=name --format=csv,noheader | grep -q . || fail "no NVIDIA GPU is visible"
# DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n 1)
# [ "${DRIVER%%.*}" -ge 535 ] || fail "NVIDIA driver $DRIVER is older than 535"

# CUDA, as PyTorch sees it.
# python3 -c 'import torch, sys; sys.exit(not torch.cuda.is_available())' || fail "torch sees no CUDA device"

# At least a number of CPUs, and of memory in GiB.
# [ "$(nproc)" -ge 4 ] || fail "fewer than 4 CPUs"
# MEMORY_GIB=$(awk '/MemTotal/ { print int($2 / 1048576) }' /proc/meminfo)
# [ "$MEMORY_GIB" -ge 16 ] || fail "less than 16 GiB of memory"

# The CPU architecture.
# [ "$(uname -m)" = x86_64 ] || fail "not an x86_64 machine"

# Free disk space in the workspace, in GiB.
# FREE_GIB=$(df -Pk . | awk 'NR == 2 { print int($4 / 1048576) }')
# [ "$FREE_GIB" -ge 20 ] || fail "less than 20 GiB free"

echo "working environment: $(uname -srm)"
exit 0
