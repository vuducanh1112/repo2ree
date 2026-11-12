#!/usr/bin/env sh
set -eu

# The claims: the run printed the greeting and its digest exactly, with the image's Python.
RESULT=result.txt
grep -Fqx 'Hello, World!' "$RESULT"
grep -Fqx 'sha256: dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f' "$RESULT"
grep -Eqx 'python: 3\.11\.[0-9]+' "$RESULT"
