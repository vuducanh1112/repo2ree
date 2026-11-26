#!/usr/bin/env sh
set -eu

# The claim: of the 31 tables the ARC holds in its run folder, its DHARMa test table aside, the workflow writes
# all, and 24 of them are the authors' own, byte for byte.
#
# 7 differ from the authors' (R 4.5.3 on Windows) in digits the platform decides: the last of a double, or those
# a GLMM's optimizer gives only to within its tolerance. They are pinned as this environment writes them.
#
# Its DHARMa test table is held without its outliers_p column, and is then the authors': testOutliers(type =
# "bootstrap") draws without a seed, so that column differs from run to run, here and in the authors' run alike.
DHARMA='runs/Fig1_plant_area_gsw_tleaf/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/Fig1_plant_area_gsw_tleaf/*.tsv' 'runs/Fig1_plant_area_gsw_tleaf/*.txt' ":(exclude)$DHARMA"; }

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
0dcd078cd7266117c7974b90d25a9ba26e89b7c59382398ada14b8e61304a11b  runs/Fig1_plant_area_gsw_tleaf/README_results.txt
7c9e540983f9a9242df424adaad081ee4afa871c53a22e2c6af1a31e38bb7311  runs/Fig1_plant_area_gsw_tleaf/REV_diagnostics/unequal_variance_sensitivity.tsv
4d6494f1112a6059cedd23cb0854ac570a8695647f5d019c196442acee7ae276  runs/Fig1_plant_area_gsw_tleaf/gsw_LMM_summary.txt
0f60b11b823632fae603173177b4b187d550d832efc243b5c101a698200175f6  runs/Fig1_plant_area_gsw_tleaf/plant_area_LMM_summary.txt
c87951e8d357c45bbdcb11299eea6a177b7ac378691404db548e5b2efc018bcb  runs/Fig1_plant_area_gsw_tleaf/plant_area_LMM_typeIII_ANOVA.tsv
2423fc33e8438590d5129378506abaed2e43d0ec92ce027689b2f8b32f6dd554  runs/Fig1_plant_area_gsw_tleaf/plant_area_estimated_marginal_means.tsv
4eace59821e90e2712ae2a281ac3b420ba01d47341924c8b8334fe85784ddef6  runs/Fig1_plant_area_gsw_tleaf/tleaf_LMM_summary.txt
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
echo "Fig1_plant_area_gsw_tleaf: 7 tables as this environment writes them, the rest as the authors wrote them"
