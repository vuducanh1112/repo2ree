#!/usr/bin/env sh
set -eu

# The claim: of the 19 tables the ARC holds in its run folder, its DHARMa test table aside, the workflow writes
# all, and 6 of them are the authors' own, byte for byte.
#
# 13 differ from the authors' (R 4.5.3 on Windows) in digits the platform decides: the last of a double, or
# those a GLMM's optimizer gives only to within its tolerance. They are pinned as this environment writes them.
#
# Its DHARMa test table is held without its outliers_p column, and is then pinned too: testOutliers(type =
# "bootstrap") draws without a seed, so that column differs from run to run, here and in the authors' run alike.
DHARMA='runs/Fig5_germination/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/Fig5_germination/*.tsv' 'runs/Fig5_germination/*.txt' ":(exclude)$DHARMA"; }

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
643b2f576f64c954b6fa2c2b719f9b9f985bac9d03e1d55480ed456c3f12fcd8  runs/Fig5_germination/Germination_LM_hybrid_statistics/germination_model_summaries_full.txt
0d6b90868cf03721a43fa94d7ddfaa1aea635437692c8f9fee2b94b554c2be99  runs/Fig5_germination/Germination_binomial_GLMM/final_day3_model_summary.txt
b2cfe159b1f12323d44f95db74e6d1b509205e9c16e3d319a6e00de35fd14e3c  runs/Fig5_germination/Germination_binomial_GLMM/germination_GLMM_NaCl_vs_PEG_minus0.6MPa.tsv
58f81bffd8045eaf38673080497fee839c9eda5180880b27ea9539c00ce874c4  runs/Fig5_germination/Germination_binomial_GLMM/germination_GLMM_anova.tsv
fcfeb81ab6d48b1b46ccd93ddaa37d14c8f3241a3432773d23053c29888d8b15  runs/Fig5_germination/Germination_binomial_GLMM/germination_GLMM_by_accession.tsv
99630e199c87b65a66ce1a5e1f878e769d276576e3b54e985b43be875475e286  runs/Fig5_germination/Germination_binomial_GLMM/germination_GLMM_lrt_threeway.tsv
4fe62035edd9a7c52c82e3309f5b806f04881d81504308f6fa6d1500dbf24503  runs/Fig5_germination/Germination_binomial_GLMM/germination_GLMM_pooled.tsv
5d4df287f0db7ddd0b3dd676de7d53b433714a08cafd36e7786d633e2799d930  runs/Fig5_germination/Germination_binomial_GLMM/germination_GLMM_probs.tsv
5c32c99dded773032db624ff790acde5222b75a8f797dc5740ab945ae10cb416  runs/Fig5_germination/Germination_binomial_GLMM/germination_PEG_minus0.6_day3_AxT_LRT.tsv
a3d1304b2e5eeda53c74f433d02e8dbfbed74ca7ac19c078ba45c6bd58380060  runs/Fig5_germination/Germination_binomial_GLMM/germination_PEG_minus0.6_day3_by_accession_Holm.tsv
8bbd3cac0d98548640aecd54b4646d9f7e401414fce93cac37a463227e7af09d  runs/Fig5_germination/Germination_binomial_GLMM/germination_PEG_minus0.6_day3_probs.tsv
fbc5372b941e986b6ba9e5bf9fd8fe5ff3d2c2d6d185bc86a0190695feffa372  runs/Fig5_germination/Germination_binomial_GLMM/speed_day1_model_summary.txt
1bf6c524a10955967f3d959ccd42b2c6185c071f74f93cd0b66c6e16decaf01b  runs/Fig5_germination/README_results.txt
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 13 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

[ "$(cut -f1-4 "$DHARMA" | sha256sum | cut -d' ' -f1)" = e776b8427e1cfe98353fb4c37bda67fff3bda5aa2740f297aa44e8eb28afb24c ] \
  || { echo "$DHARMA differs from what is expected of it, outliers_p aside" >&2; exit 1; }
echo "Fig5_germination: 13 tables as this environment writes them, the rest as the authors wrote them"
