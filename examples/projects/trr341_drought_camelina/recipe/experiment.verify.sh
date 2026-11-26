#!/usr/bin/env sh
set -eu

# The claim: the workflows write the ARC's tables, 303 of them, from the data it keeps in Git LFS, and all
# but 68 of those they write are the authors' own, byte for byte, or in the case of six of the seven DHARMa
# test tables, but for one column. The 68 differ from the authors' (R 4.5.3 on Windows, by the workflows'
# own notes) in digits the platform decides: the last of a double, or the sixth to eighth of a GLMM's fit, which
# its optimizer gives to within its tolerance, and two README texts name an assay folder as it was spelt
# before the ARC renamed it. They are pinned as this environment writes them.
#
# 21 of the tables the ARC holds no workflow writes: the supplement's Tables S1 to S3, which the ARC's README
# says were extracted from the submitted supplement, and eighteen figure tables of Manuscript_figures under
# names its script no longer gives them (Fig1A_..., where it now writes Fig1_A_...). The experiment deletes the
# tables first, so these read as deleted, and are named here.
#
# The DHARMa test tables are held without their outliers_p column: testOutliers(type = "bootstrap") draws
# without a seed (simulateResiduals seeds its own draws, then puts the session's random state back), so that
# column differs from run to run, here and in the authors' run alike.
DHARMA='*/DHARMa_tests_all_models.tsv'
# Pathspecs, quoted so the shell leaves their globs to git, which matches them across directories.
tables() { git diff "$@" -- 'runs/*.tsv' 'runs/*.txt' ":(exclude)runs/$DHARMA"; }

DELETED="runs/Manuscript_figures/Fig1A_physiology_plant_area_EMMs.tsv
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
runs/Manuscript_figures/Table_S3_associations_germination.tsv"
if [ "$(tables --name-only --diff-filter=D)" != "$DELETED" ]; then
  echo "the tables no workflow writes are not the 21 expected:" >&2
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
fb7da8d19d1eb31aef99ed8a8106dd8a373a63c1370d523075140490edb9b9d2  runs/Fig2_yield_seedweight_seedsize/README_results.txt
b32a0ca69627b473fe180f53d25a4d40c79ebbdf8cca1c6cfce8df47214d408e  runs/Fig2_yield_seedweight_seedsize/REV_diagnostics/unequal_variance_sensitivity.tsv
71d2597d952dbdf14fa2b3c8caec1a02ecc7a78953f7cb8afca5a11c3e9662e0  runs/Fig2_yield_seedweight_seedsize/seed_area_model_ANOVA.tsv
fa07daaae457400eb13dc6fa4b20fb4ada2c9184993f595445fc4778b7c2160d  runs/Fig2_yield_seedweight_seedsize/seed_area_model_summary.txt
d70bb7e0a55fdaf8fd1dbd69bb4906aa94dca886be3fd4594899fc2b7deab858  runs/Fig2_yield_seedweight_seedsize/seed_number_model_summary.txt
ecaacd2e42d8bdd6c79d72fd9f209026eb32309aab28e3002ad62a6a471204da  runs/Fig2_yield_seedweight_seedsize/seed_weight_model_summary.txt
474631f829162dc9991359d38492c930902cccc01d0cb93faff97479fdd250eb  runs/Fig2_yield_seedweight_seedsize/yield_model_summary.txt
0c89843f26d4db0850de16be60e2981b8600d44fa8172d75ff070201a958504e  runs/Fig3_mucilage_stem_class/REV_diagnostics/unequal_variance_sensitivity.tsv
7fbf4518f70dd3278a92613b69be4592235b0ed03c7406d8edf177c47e2a415c  runs/Fig3_mucilage_stem_class/total_mucilage/README_results_total_mucilage.txt
a3207d28ef51de459ff135c2cd4a0f429b9f37b9fe36b023b2e873a9377f2949  runs/Fig3_mucilage_stem_class/total_mucilage/total_mucilage_by_stem_class_LMM_typeIII_ANOVA_by_line.tsv
e27be274ddc20c8c6adff5da3be3d1f3b629a9d84b7665e964eb8b8f1d3338cf  runs/Fig3_mucilage_stem_class/total_mucilage_ratio/README_results_total_mucilage_ratio.txt
c611565c75a73176c2e5fc89661e7a0ad71b4c390976ff62b4fa3251b31ff8cc  runs/Fig3_mucilage_stem_class/total_mucilage_ratio/total_mucilage_ratio_by_stem_class_LMM_typeIII_ANOVA_by_line.tsv
887a4c6844bcfe4d5d9fef1fb349884f678b9bcd24ec7ba473c8b3d9b6e5c2fc  runs/Fig3_seed_mucilage/README_results_LMM_brackets.txt
e2bbc7b3ca1b9575e798488fdf9d2263e5d1ccde02e200375f702b19dfbb1763  runs/Fig3_seed_mucilage/REV_diagnostics/unequal_variance_sensitivity.tsv
783b6cb33503744a66ff52420f477c6f82f5c513e42ea756024f982ec373fa8f  runs/Fig3_seed_mucilage/total_mucilage_LMM_summary.txt
08bfd33fbf212b54f74c8414c938a8e13b92fa0908d1b207cc259b9a4b7b7522  runs/Fig3_seed_mucilage/total_mucilage_LMM_typeIII_ANOVA.tsv
5c4a6b5ab52d7c6bd494df895cf821ca368dd7ffb1c140549e06906d19e13dae  runs/Fig3_seed_mucilage/total_mucilage_ratio_LMM_summary.txt
65f01a67e3103654dd90775a4072a5a40b55e043224e48d70f22217da44d22b0  runs/Fig3_seed_mucilage/total_mucilage_ratio_LMM_typeIII_ANOVA.tsv
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
ce3c8e164bc1c40796fc498c6cc9a7f3df0b1ff6476e4c443cc5796bb6b11d63  runs/Manuscript_figures/FigS4_drought_effect_by_accession_stem_class_Holm.tsv
53fbf25f8ca1be9d696b64cdba6c61fcb90e860d8c84f967322148572261698c  runs/Manuscript_figures/FigS5_PCA_loadings.tsv
d1912abadd68ff3860b010fc7e61d9c4dbf9d13264f490edbed290b831e6e79d  runs/Manuscript_figures/FigS5_PCA_scores.tsv
2d2d5ce484431ec41dc39808f26724892d7aa1e98ad6717b6218c70277b0e723  runs/Manuscript_figures/FigS5_dispersion_test_treatment.tsv
ad1f40a6ac676984fc13b5109005031cae4f740a44b3d70044ef680bab2b351a  runs/TabS2_stem_count_ANCOVA/ANCOVA_TypeIII.tsv
4e5b48e51721adc4d9681b5581b7e25c284ed1204ddb266261fd6f57ff835782  runs/TabS2_stem_count_ANCOVA/ANCOVA_drought_effect_by_accession.tsv
e0fd95239337c8aa20999f0d231104b7d509f3dc46dea972838d6355a49cace5  runs/TabS2_stem_count_ANCOVA/ANCOVA_drought_effect_pooled.tsv
8e88301346487c289ba92b04ad1efb03ed3657273f48f88f40af631792c604aa  runs/TabS2_stem_count_ANCOVA/ANCOVA_slopes.tsv
fbf984b15b987bf8fcb9b0b1bd1643db524f08b770d3286588375fccb96e88a6  runs/TabS3_mucilage_germination/H2_mucilage_germination.tsv
EOF
)
if [ "$(tables --name-only --diff-filter=M)" != "$(printf '%s\n' "$MODIFIED" | sed 's/^[0-9a-f]*  //')" ]; then
  echo "the tables that differ from the authors' are not the 68 expected:" >&2
  tables --name-status --diff-filter=M >&2
  exit 1
fi
printf '%s\n' "$MODIFIED" | sha256sum --check --strict --quiet

for table in $(git ls-files "runs/$DHARMA"); do
  written=$(cut -f1-4 "$table")
  case "$table" in
    runs/Fig5_germination/*) expected=e776b8427e1cfe98353fb4c37bda67fff3bda5aa2740f297aa44e8eb28afb24c; [ "$(printf '%s\n' "$written" | sha256sum | cut -d' ' -f1)" = "$expected" ] ;;
    *) [ "$written" = "$(git show "HEAD:$table" | cut -f1-4)" ] ;;
  esac || { echo "$table differs from what is expected of it, outliers_p aside" >&2; exit 1; }
done
echo "the runs hold: 68 tables as this environment writes them, the rest as the authors wrote them"
