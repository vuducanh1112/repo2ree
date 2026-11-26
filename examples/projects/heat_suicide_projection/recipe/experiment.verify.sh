#!/usr/bin/env sh
set -eu

# The claim: every stage regenerates the results the capsule holds for it, from the observed data, to within
# what its computation decides. The first stage's city fits are the authors' to within the last digits of a
# double, the modeled suicide counts and the meta-regression's variables are theirs exactly, and the second
# stage's meta-analysis, which REML fits by optimisation, is theirs to within its optimiser's tolerance (2.6e-4
# at most, in the fitted model, 4.3e-6 in what it predicts). The projection's estimates carry that on: theirs
# to within 2e-6 for a region and 1e-4 for a city. Its confidence bounds are not: the projection draws them by
# Monte Carlo, 1,000 draws a city, scenario and climate model, seeded, but through MASS::mvrnorm, whose draws
# pass through an eigendecomposition the machine's BLAS and LAPACK compute, and they differ from the authors'
# by a few percent for a region and up to 91 % for a city's relative bound near zero. This environment computes
# all of it alike every run: every number the run writes is pinned, in results/values.tsv, and how far each is
# from the authors', in results/agreement.tsv.
AGREEMENT=results/agreement.tsv
[ -f "$AGREEMENT" ] || { echo "the run wrote no $AGREEMENT" >&2; exit 1; }

# Columns: file, object, slice, values, differing, max_abs_diff, max_rel_diff. Numbers with a decimal point.
# Each object or slice that is not a Monte Carlo bound is held to its bound, ten times what it is here.
LC_ALL=C awk -F '\t' '
  BEGIN {
    within["coefall all"] = 1e-11; within["vcovall all"] = 1e-10
    within["mvoverall all"] = 3e-3; within["mvpred all"] = 2e-5; within["blupres all"] = 5e-5
    within["predcoefs all"] = 2e-5; within["predvcov_mat all"] = 3e-6
    within["metavariable all"] = 0; within["suicideproj all"] = 0
    within["anabs est"] = 1e-5; within["afabs est"] = 1e-5; within["anrel est"] = 2e-5; within["afrel est"] = 2e-5
    within["anabs_city est"] = 1e-3; within["afabs_city est"] = 1e-3
    within["anrel_city est"] = 3e-4; within["afrel_city est"] = 3e-4
  }
  NR == 1 { next }
  $4 == "NA" || $7 == "NA" { print "no comparison for " $2 " " $3 ": the objects differ in shape" > "/dev/stderr"; bad = 1; next }
  $3 == "ci.l" || $3 == "ci.u" { next }
  !(($2 " " $3) in within) { print "no bound for " $2 " " $3 > "/dev/stderr"; bad = 1; next }
  $7 + 0 > within[$2 " " $3] { print $2 " " $3 " is " $7 " apart from the authors'\''" > "/dev/stderr"; bad = 1 }
  { held++ }
  END { if (held != 17) { print "expected 17 objects and slices to hold, found " held + 0 > "/dev/stderr"; bad = 1 }; exit bad }
' "$AGREEMENT"

sha256sum --check --strict <<'PINNED'
4ae774d9eb8832feece8a7e780ec9ced3de2473da0e19c526410c7bcc1de0c1f  results/values.tsv
8b274f32356e20deedf255d847205672fe46ead6fe1a9c36f66b0323d14e30f4  results/agreement.tsv
PINNED
