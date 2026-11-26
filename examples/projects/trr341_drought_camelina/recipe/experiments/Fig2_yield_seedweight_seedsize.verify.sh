#!/usr/bin/env sh
set -eu

# The claim: of the 25 tables the ARC holds in its run folder, its DHARMa test table aside, the workflow writes
# all, and 18 of them are the authors' own, byte for byte.
#
# 7 differ from the authors' (R 4.5.3 on Windows) in digits the platform decides: the last of a double, or those
# a GLMM's optimizer gives only to within its tolerance. They are pinned as this environment writes them.
#
# Its DHARMa test table is held without its outliers_p column, and is then the authors': testOutliers(type =
# "bootstrap") draws without a seed, so that column differs from run to run, here and in the authors' run alike.
DHARMA='runs/Fig2_yield_seedweight_seedsize/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/Fig2_yield_seedweight_seedsize/*.tsv' 'runs/Fig2_yield_seedweight_seedsize/*.txt' ":(exclude)$DHARMA"; }

if [ "$(tables --name-only --diff-filter=D)" != "" ]; then
  echo "tables the workflow should write are missing:" >&2
  tables --name-status --diff-filter=D >&2
  exit 1
fi
if [ -n "$(tables --name-only --diff-filter=ACRTUXB)" ]; then
  echo "the tables changed in other ways than in content:" >&2
  tables --name-status --diff-filter=ACRTUXB >&2
  exit 1
fi

MODIFIED=$(cat <<'EOF'
fb7da8d19d1eb31aef99ed8a8106dd8a373a63c1370d523075140490edb9b9d2  runs/Fig2_yield_seedweight_seedsize/README_results.txt
b32a0ca69627b473fe180f53d25a4d40c79ebbdf8cca1c6cfce8df47214d408e  runs/Fig2_yield_seedweight_seedsize/REV_diagnostics/unequal_variance_sensitivity.tsv
71d2597d952dbdf14fa2b3c8caec1a02ecc7a78953f7cb8afca5a11c3e9662e0  runs/Fig2_yield_seedweight_seedsize/seed_area_model_ANOVA.tsv
fa07daaae457400eb13dc6fa4b20fb4ada2c9184993f595445fc4778b7c2160d  runs/Fig2_yield_seedweight_seedsize/seed_area_model_summary.txt
d70bb7e0a55fdaf8fd1dbd69bb4906aa94dca886be3fd4594899fc2b7deab858  runs/Fig2_yield_seedweight_seedsize/seed_number_model_summary.txt
ecaacd2e42d8bdd6c79d72fd9f209026eb32309aab28e3002ad62a6a471204da  runs/Fig2_yield_seedweight_seedsize/seed_weight_model_summary.txt
474631f829162dc9991359d38492c930902cccc01d0cb93faff97479fdd250eb  runs/Fig2_yield_seedweight_seedsize/yield_model_summary.txt
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 7 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

[ "$(cut -f1-4 "$DHARMA")" = "$(git show "HEAD:$DHARMA" | cut -f1-4)" ] \
  || { echo "$DHARMA differs from what is expected of it, outliers_p aside" >&2; exit 1; }
echo "Fig2_yield_seedweight_seedsize: 7 tables as this environment writes them, the rest as the authors wrote them"
