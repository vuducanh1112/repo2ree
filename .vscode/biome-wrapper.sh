#!/usr/bin/env bash
exec nix develop --command ./src/repo2ree/web/node_modules/@biomejs/biome/bin/biome "$@"