#!/usr/bin/env sh
set -eu

# The gate every commit passes: the static checks, the docs build and every container-free unit suite.
# On success it writes .receipts/commit-gate.json, naming the tree it passed on.
just commit-gate
