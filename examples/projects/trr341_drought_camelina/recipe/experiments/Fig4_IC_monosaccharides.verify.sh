#!/usr/bin/env sh
set -eu

# The claim: of the 112 tables the ARC holds in its run folder, its DHARMa test table aside, the workflow writes
# all, and 101 of them are the authors' own, byte for byte.
#
# 11 differ from the authors' (R 4.5.3 on Windows) in digits the platform decides: the last of a double, or
# those a GLMM's optimizer gives only to within its tolerance. They are pinned as this environment writes them.
#
# Its DHARMa test table is held without its outliers_p column, and is then the authors': testOutliers(type =
# "bootstrap") draws without a seed, so that column differs from run to run, here and in the authors' run alike.
DHARMA='runs/Fig4_IC_monosaccharides/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/Fig4_IC_monosaccharides/*.tsv' 'runs/Fig4_IC_monosaccharides/*.txt' ":(exclude)$DHARMA"; }

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
3ce1b6d1292aa8c86f8165beb0e8d0403d456794823b0facca018e318f191947  runs/Fig4_IC_monosaccharides/ALL_monosaccharides_TypeIII_ANOVA.tsv
1baada4dd94dfd03c9dcc0c7c394d5ca29c8fba3c513f8f69820ec1afca2d61a  runs/Fig4_IC_monosaccharides/Ara/Ara_EMM_line.tsv
48f9a4aa9089916eed6580e1426aef4ae87387073e2f45b33f6cfdc5f28d1372  runs/Fig4_IC_monosaccharides/Fuc/Fuc_TypeIII_ANOVA.tsv
5c6e84cfa72f5a6ee77709cee9350e3ec56336528d1b5a7f316153a2ae80dd9e  runs/Fig4_IC_monosaccharides/Gal/Gal_TypeIII_ANOVA.tsv
3cd04bfad32f87de8ca00b3fb55415804dad9f2b5f3f6bc5b228bdc4ecbf0691  runs/Fig4_IC_monosaccharides/Glc/Glc_TypeIII_ANOVA.tsv
d76253f18c4f8845d2f381117416cf6ea745fd7d7cd3bff6968ad94eb1076bfb  runs/Fig4_IC_monosaccharides/GlcA/GlcA_TypeIII_ANOVA.tsv
710c01305d6a1157feea479029375445cb5fea754767d69a680a0dfbc3853b0a  runs/Fig4_IC_monosaccharides/Man/Man_EMM_all_combinations.tsv
182a8de4f2c066fa8cded502ec2586bdfa14fb273f3c9aed5ab2dde2cd38f981  runs/Fig4_IC_monosaccharides/Man/Man_EMM_treatment_by_line_mucilage.tsv
901a9e747e7412e8594d24b130e9a92d61eebec60c79ddd5df5003bbdec92949  runs/Fig4_IC_monosaccharides/README_analysis.txt
2dce7623def9cc5f98506624777831772aaa20e7c1c64bcd415a2b8afb3d50e7  runs/Fig4_IC_monosaccharides/REV_diagnostics/unequal_variance_sensitivity.tsv
707f63929746f07024d3ae7f179a306009844a064cf33267b9410e6101fc31e2  runs/Fig4_IC_monosaccharides/Xyl/Xyl_TypeIII_ANOVA.tsv
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 11 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

[ "$(cut -f1-4 "$DHARMA")" = "$(git show "HEAD:$DHARMA" | cut -f1-4)" ] \
  || { echo "$DHARMA differs from what is expected of it, outliers_p aside" >&2; exit 1; }
echo "Fig4_IC_monosaccharides: 11 tables as this environment writes them, the rest as the authors wrote them"
