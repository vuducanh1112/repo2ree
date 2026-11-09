#!/usr/bin/env sh
set -eu

# The claim: the estimate is within 0.05 of pi, some 13 standard errors at this
# sample size. The exact digits change on every run and are no part of the claim.
RESULT=result.txt
awk '/^pi estimate: / { difference = $3 - 3.141593; within = difference >= -0.05 && difference <= 0.05 }
     END { exit !within }' "$RESULT"
