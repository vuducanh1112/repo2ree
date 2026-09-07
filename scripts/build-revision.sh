#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel 2>/dev/null) || { printf '%s\n' development; exit 0; }
revision=$(git -C "$root" rev-parse HEAD)
if ! git -C "$root" diff --quiet || ! git -C "$root" diff --cached --quiet || [ -n "$(git -C "$root" ls-files --others --exclude-standard)" ]; then
  revision="${revision}-dirty"
fi
printf '%s\n' "$revision"
