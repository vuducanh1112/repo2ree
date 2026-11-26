#!/usr/bin/env sh
set -eu

# The claim: of the 13 tables the ARC holds in its run folder, its DHARMa test table aside, the workflow writes
# all, and 8 of them are the authors' own, byte for byte.
#
# 5 differ from the authors' (R 4.5.3 on Windows) in digits the platform decides: the last of a double, or those
# a GLMM's optimizer gives only to within its tolerance. They are pinned as this environment writes them.
#
# Its DHARMa test table is held without its outliers_p column, and is then the authors': testOutliers(type =
# "bootstrap") draws without a seed, so that column differs from run to run, here and in the authors' run alike.
DHARMA='runs/Fig3_mucilage_stem_class/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/Fig3_mucilage_stem_class/*.tsv' 'runs/Fig3_mucilage_stem_class/*.txt' ":(exclude)$DHARMA"; }

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
0c89843f26d4db0850de16be60e2981b8600d44fa8172d75ff070201a958504e  runs/Fig3_mucilage_stem_class/REV_diagnostics/unequal_variance_sensitivity.tsv
7fbf4518f70dd3278a92613b69be4592235b0ed03c7406d8edf177c47e2a415c  runs/Fig3_mucilage_stem_class/total_mucilage/README_results_total_mucilage.txt
a3207d28ef51de459ff135c2cd4a0f429b9f37b9fe36b023b2e873a9377f2949  runs/Fig3_mucilage_stem_class/total_mucilage/total_mucilage_by_stem_class_LMM_typeIII_ANOVA_by_line.tsv
e27be274ddc20c8c6adff5da3be3d1f3b629a9d84b7665e964eb8b8f1d3338cf  runs/Fig3_mucilage_stem_class/total_mucilage_ratio/README_results_total_mucilage_ratio.txt
c611565c75a73176c2e5fc89661e7a0ad71b4c390976ff62b4fa3251b31ff8cc  runs/Fig3_mucilage_stem_class/total_mucilage_ratio/total_mucilage_ratio_by_stem_class_LMM_typeIII_ANOVA_by_line.tsv
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 5 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

[ "$(cut -f1-4 "$DHARMA")" = "$(git show "HEAD:$DHARMA" | cut -f1-4)" ] \
  || { echo "$DHARMA differs from what is expected of it, outliers_p aside" >&2; exit 1; }
echo "Fig3_mucilage_stem_class: 5 tables as this environment writes them, the rest as the authors wrote them"
