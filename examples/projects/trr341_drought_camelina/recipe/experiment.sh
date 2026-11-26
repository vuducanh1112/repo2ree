#!/usr/bin/env sh
set -eu

# The ARC's tables go first, so the verify sees only what this run writes: a table no workflow writes is
# missing, not the authors' copy.
find runs -type f \( -name '*.tsv' -o -name '*.txt' \) -delete

# Every R workflow of the ARC in one run, each as its workflow.cwl runs it, in the order their inputs need: TabS3
# reads Fig4's means as this run writes them, and Manuscript_figures the runs of all the others. The experiments
# of one workflow each read the authors' instead.
for workflow in \
  Fig1_plant_area_gsw_tleaf Fig2_secondary_stems Fig2_yield_seedweight_seedsize Fig3_mucilage_stem_class \
  Fig3_seed_mucilage Fig4_IC_monosaccharides Fig5_germination TabS1_germination_AxT_by_condition \
  TabS2_stem_count_ANCOVA TabS3_mucilage_germination Manuscript_figures; do
  echo "== $workflow"
  Rscript "workflows/$workflow/$workflow.R"
done
