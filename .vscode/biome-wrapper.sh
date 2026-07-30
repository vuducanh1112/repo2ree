#!/usr/bin/env bash
exec nix develop --command ./gui/node_modules/@biomejs/biome/bin/biome "$@"