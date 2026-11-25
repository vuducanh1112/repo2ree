#!/usr/bin/env sh
set -eu

# The claim: the commit gate passed on exactly the source this REE pins, commit
# 7235286f87edb7e53aff71e25ca59827f8dc28b1 of https://github.com/vuducanh1112/repo2ree.git, whose tree
# this is. Its receipt is the gate's own record; the time it was written differs on every run.
RECEIPT=.receipts/commit-gate.json
EXPECTED_TREE=86dc9d88c119b587a8796fb6b7a77b5c46cf0dc7

grep -Eq '"gate": *"commit-gate"' "$RECEIPT"
grep -Eq "\"tree\": *\"$EXPECTED_TREE\"" "$RECEIPT"
