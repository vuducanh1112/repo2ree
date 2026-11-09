#!/bin/sh
# Hello world in a container image: fixed output, so an experiment can verify it exactly
# and a reviewer's rerun prints the same bytes as the instant Python project does.
echo "--- Instant Docker Hello World ---"
echo "Hello, World!"
printf '%s' "Hello, World!" | sha256sum | sed 's/ .*//; s/^/sha256: /'
