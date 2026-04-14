#!/usr/bin/env bash
exec nix develop --command ./frontend/node_modules/@biomejs/biome/bin/biome "$@"