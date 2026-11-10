#!/usr/bin/env sh
set -eu

RESULT=result.txt
grep -Fqx 'product: [4, 10, 14]' "$RESULT"
grep -Fqx 'trace of square: 33' "$RESULT"
grep -Fqx 'environment: /tmp/ree-conda-runtime/env' "$RESULT"
