#!/usr/bin/env sh
set -eu

# The claim: of the 14 tables the ARC holds in its run folder, its DHARMa test table aside, the workflow writes
# all, and 8 of them are the authors' own, byte for byte.
#
# 6 differ from the authors' (R 4.5.3 on Windows) in digits the platform decides: the last of a double, or those
# a GLMM's optimizer gives only to within its tolerance. They are pinned as this environment writes them.
#
# Its DHARMa test table is held without its outliers_p column, and is then the authors': testOutliers(type =
# "bootstrap") draws without a seed, so that column differs from run to run, here and in the authors' run alike.
DHARMA='runs/Fig3_seed_mucilage/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/Fig3_seed_mucilage/*.tsv' 'runs/Fig3_seed_mucilage/*.txt' ":(exclude)$DHARMA"; }

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
887a4c6844bcfe4d5d9fef1fb349884f678b9bcd24ec7ba473c8b3d9b6e5c2fc  runs/Fig3_seed_mucilage/README_results_LMM_brackets.txt
e2bbc7b3ca1b9575e798488fdf9d2263e5d1ccde02e200375f702b19dfbb1763  runs/Fig3_seed_mucilage/REV_diagnostics/unequal_variance_sensitivity.tsv
783b6cb33503744a66ff52420f477c6f82f5c513e42ea756024f982ec373fa8f  runs/Fig3_seed_mucilage/total_mucilage_LMM_summary.txt
08bfd33fbf212b54f74c8414c938a8e13b92fa0908d1b207cc259b9a4b7b7522  runs/Fig3_seed_mucilage/total_mucilage_LMM_typeIII_ANOVA.tsv
5c4a6b5ab52d7c6bd494df895cf821ca368dd7ffb1c140549e06906d19e13dae  runs/Fig3_seed_mucilage/total_mucilage_ratio_LMM_summary.txt
65f01a67e3103654dd90775a4072a5a40b55e043224e48d70f22217da44d22b0  runs/Fig3_seed_mucilage/total_mucilage_ratio_LMM_typeIII_ANOVA.tsv
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 6 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

[ "$(cut -f1-4 "$DHARMA")" = "$(git show "HEAD:$DHARMA" | cut -f1-4)" ] \
  || { echo "$DHARMA differs from what is expected of it, outliers_p aside" >&2; exit 1; }
echo "Fig3_seed_mucilage: 6 tables as this environment writes them, the rest as the authors wrote them"
