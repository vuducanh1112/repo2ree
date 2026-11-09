#!/usr/bin/env sh
set -eu

grep -Fq '"greeting": "Hello"' result.txt
