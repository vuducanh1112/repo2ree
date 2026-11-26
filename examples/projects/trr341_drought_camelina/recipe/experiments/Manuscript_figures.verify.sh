#!/usr/bin/env sh
set -eu

# The claim: of the 29 tables the ARC holds in its run folder, the workflow writes 8, and 4 of them are the
# authors' own, byte for byte.
#
# 4 differ from the authors' (R 4.5.3 on Windows) in digits the platform decides: the last of a double, or those
# a GLMM's optimizer gives only to within its tolerance. They are pinned as this environment writes them.
#
# The 21 it does not write: the supplement's Tables S1 to S3, which the ARC's README says were extracted from
# the submitted supplement, and eighteen figure tables under names the script no longer gives them (Fig1A_...,
# where it now writes Fig1_A_...). They read as deleted.
DHARMA='runs/Manuscript_figures/REV_diagnostics/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/Manuscript_figures/*.tsv' 'runs/Manuscript_figures/*.txt' ":(exclude)$DHARMA"; }

if [ "$(tables --name-only --diff-filter=D)" != "runs/Manuscript_figures/Fig1A_physiology_plant_area_EMMs.tsv
runs/Manuscript_figures/Fig1B_physiology_leaf_temperature_EMMs.tsv
runs/Manuscript_figures/Fig1B_physiology_leaf_temperature_drought_effect.tsv
runs/Manuscript_figures/Fig1B_physiology_leaf_temperature_drought_effect_by_accession_Holm.tsv
runs/Manuscript_figures/Fig1C_physiology_gsw_EMMs.tsv
runs/Manuscript_figures/Fig1C_physiology_gsw_drought_effect.tsv
runs/Manuscript_figures/Fig2_drought_effects_pooled.tsv
runs/Manuscript_figures/Fig3AB_mucilage_EMMs_by_accession.tsv
runs/Manuscript_figures/Fig3AB_mucilage_drought_effect_by_accession.tsv
runs/Manuscript_figures/Fig3CD_mucilage_drought_effect_by_stem_class.tsv
runs/Manuscript_figures/Fig4A_composition_EMMs.tsv
runs/Manuscript_figures/Fig4A_fraction_difference_paired.tsv
runs/Manuscript_figures/Fig4B_drought_effect_pooled.tsv
runs/Manuscript_figures/Fig4CDE_drought_effect_by_accession_Holm.tsv
runs/Manuscript_figures/Fig5_germination_BC_drought_odds_ratios.tsv
runs/Manuscript_figures/Fig5_germination_BC_modelled_probabilities.tsv
runs/Manuscript_figures/Fig5_germination_D_PEG_minus0.6_drought_OR_by_accession_Holm.tsv
runs/Manuscript_figures/Fig5_germination_D_PEG_minus0.6_probabilities.tsv
runs/Manuscript_figures/Table_S1_statistical_tests.tsv
runs/Manuscript_figures/Table_S2_ANCOVA_covariates.tsv
runs/Manuscript_figures/Table_S3_associations_germination.tsv" ]; then
  echo "the tables the workflow does not write are not the 21 expected:" >&2
  tables --name-status --diff-filter=D >&2
  exit 1
fi
if [ -n "$(tables --name-only --diff-filter=ACRTUXB)" ]; then
  echo "the tables changed in other ways than in content:" >&2
  tables --name-status --diff-filter=ACRTUXB >&2
  exit 1
fi

MODIFIED=$(cat <<'EOF'
ce3c8e164bc1c40796fc498c6cc9a7f3df0b1ff6476e4c443cc5796bb6b11d63  runs/Manuscript_figures/FigS4_drought_effect_by_accession_stem_class_Holm.tsv
53fbf25f8ca1be9d696b64cdba6c61fcb90e860d8c84f967322148572261698c  runs/Manuscript_figures/FigS5_PCA_loadings.tsv
d1912abadd68ff3860b010fc7e61d9c4dbf9d13264f490edbed290b831e6e79d  runs/Manuscript_figures/FigS5_PCA_scores.tsv
2d2d5ce484431ec41dc39808f26724892d7aa1e98ad6717b6218c70277b0e723  runs/Manuscript_figures/FigS5_dispersion_test_treatment.tsv
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 4 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

echo "Manuscript_figures: 4 tables as this environment writes them, the rest as the authors wrote them"
