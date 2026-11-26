#!/usr/bin/env sh
set -eu

# The claim: the run writes every table the package ships, 49 of them besides its session record, and all but
# four are the authors' own, byte for byte. The four differ from the authors' (R 4.5.2 on an arm64 Mac, by
# output/sessionInfo.txt) in their last digits: the p-curve calculations, its figure numbers, two Stouffer
# statistics (192.4937 and 239.7375 here 192.4939 and 239.7384), and one robustness p-value (0.0313 here
# 0.0312). They are pinned as this environment writes them. A table the run did not write reads as deleted.
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'output/*.tex' 'output/*.txt' ':(exclude)output/sessionInfo.txt'; }
DIFFERING=$(tables --name-only)
EXPECTED="output/pcurve/Calculations_example.txt
output/pcurve/FigNumbers_example.txt
output/pcurve/STOUFFER_example.txt
output/tables/randomization_test/robustness/random/random_one_1.tex"

if [ "$DIFFERING" != "$EXPECTED" ]; then
  echo "the tables that differ from the authors' are not the four expected:" >&2
  tables --name-status >&2
  exit 1
fi

sha256sum --check --strict <<'EOF'
eb18bd103d3cc0f2ea1cce40e1fe510558f06658a93aa824048fdd1d905475e4  output/pcurve/Calculations_example.txt
018b9beb4315558a2669594e9237e469e574344e4eb69ddcd15842f53429030d  output/pcurve/FigNumbers_example.txt
62e83b479a7db0651785ae15df130d414a69863298cff1f17bb33e401d1c4a4e  output/pcurve/STOUFFER_example.txt
bf7a77737364977ba5a797c5ba43cdab3c8bbf2ddefd99be6e34dadecc2a636d  output/tables/randomization_test/robustness/random/random_one_1.tex
EOF
