#!/usr/bin/env sh
set -eu

# The claim: of the 36 tables the ARC holds in its run folder, its DHARMa test table aside, the workflow writes
# all, and 26 of them are the authors' own, byte for byte.
#
# 10 differ from the authors' (R 4.5.3 on Windows) in digits the platform decides: the last of a double, or
# those a GLMM's optimizer gives only to within its tolerance. They are pinned as this environment writes them.
#
# Its DHARMa test table is held without its outliers_p column, and is then the authors': testOutliers(type =
# "bootstrap") draws without a seed, so that column differs from run to run, here and in the authors' run alike.
DHARMA='runs/Fig2_secondary_stems/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/Fig2_secondary_stems/*.tsv' 'runs/Fig2_secondary_stems/*.txt' ":(exclude)$DHARMA"; }

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
8e444ecd3f90e20f1acecf77393959b02221e4816e37684522bcb27dab338928  runs/Fig2_secondary_stems/REV_diagnostics/unequal_variance_sensitivity.tsv
dbccc08e51ecc3a5ee79f04bd2e05ce92003460a6563b2b21aae1d1afeb27099  runs/Fig2_secondary_stems/inflorescence_length_model_ANOVA_type3.tsv
de417df980e7f8acfd85b052c7f87b739489a8792689179269023ed1b6d90077  runs/Fig2_secondary_stems/inflorescence_length_model_summary.txt
c914ae3d9f6b5dd34568ab14e8174fbb0a39e9fbc9aa6427356b5d7f66f6d4ef  runs/Fig2_secondary_stems/internode_distance_model_ANOVA_type3.tsv
055f714a4a1fa94b6d595c9c64e2bb1a9c8e7fa231c00e47012dfe0c90af1c51  runs/Fig2_secondary_stems/internode_distance_model_summary.txt
822a42676ac28dbdae95819f558a43e7026b88bb46f93adf6796aeb8d1586051  runs/Fig2_secondary_stems/main_stem_diameter_ratio_model_summary.txt
1ee35cd825206de2968442e8cf753daa33a2546c2f596682ab34e0a4dba5e7cf  runs/Fig2_secondary_stems/secondary_stem_density_model_summary.txt
849ac388474862a37037201e605791c3cba4b9d2801040f38497607d2cce7a8a  runs/Fig2_secondary_stems/secondary_stem_length_model_summary.txt
6d7536f62e2b1e4ce8036cc6d51b32e9650ce665826e6b9503bd91e824268320  runs/Fig2_secondary_stems/secondary_stem_length_significance_brackets.tsv
ef400a87bf027836088743015f2b762571a5cb83286ac252bf1efc2b2681e2d3  runs/Fig2_secondary_stems/secondary_stem_length_treatment_comparisons_within_accession_holm.tsv
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 10 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

[ "$(cut -f1-4 "$DHARMA")" = "$(git show "HEAD:$DHARMA" | cut -f1-4)" ] \
  || { echo "$DHARMA differs from what is expected of it, outliers_p aside" >&2; exit 1; }
echo "Fig2_secondary_stems: 10 tables as this environment writes them, the rest as the authors wrote them"
