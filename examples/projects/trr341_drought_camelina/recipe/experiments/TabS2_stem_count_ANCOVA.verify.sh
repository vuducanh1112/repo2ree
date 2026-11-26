#!/usr/bin/env sh
set -eu

# The claim: of the 15 tables the ARC holds in its run folder, the workflow writes all, and 11 of them are the
# authors' own, byte for byte.
#
# 4 differ from the authors' (R 4.5.3 on Windows) in digits the platform decides: the last of a double, or those
# a GLMM's optimizer gives only to within its tolerance. They are pinned as this environment writes them.
DHARMA='runs/TabS2_stem_count_ANCOVA/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/TabS2_stem_count_ANCOVA/*.tsv' 'runs/TabS2_stem_count_ANCOVA/*.txt' ":(exclude)$DHARMA"; }

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
ad1f40a6ac676984fc13b5109005031cae4f740a44b3d70044ef680bab2b351a  runs/TabS2_stem_count_ANCOVA/ANCOVA_TypeIII.tsv
4e5b48e51721adc4d9681b5581b7e25c284ed1204ddb266261fd6f57ff835782  runs/TabS2_stem_count_ANCOVA/ANCOVA_drought_effect_by_accession.tsv
e0fd95239337c8aa20999f0d231104b7d509f3dc46dea972838d6355a49cace5  runs/TabS2_stem_count_ANCOVA/ANCOVA_drought_effect_pooled.tsv
8e88301346487c289ba92b04ad1efb03ed3657273f48f88f40af631792c604aa  runs/TabS2_stem_count_ANCOVA/ANCOVA_slopes.tsv
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 4 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

echo "TabS2_stem_count_ANCOVA: 4 tables as this environment writes them, the rest as the authors wrote them"
