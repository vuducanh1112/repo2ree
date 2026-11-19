// Generated from contracts/openapi.json by `python -m scripts.contracts write gui-vocabulary`. Do not edit.

/** #/components/schemas/ReeStepState/properties/key/enum */
export const STEP_KEYS = [
  "acquire_source",
  "metadata",
  "observe_hardware",
  "check_working_environment",
  "evaluate_reproducibility",
  "build_experiment_environment",
  "generate_sbom",
  "cross_check_sbom",
  "activate_experiment_environment",
  "experiments",
  "seal_ree",
] as const;
export type StepKey = (typeof STEP_KEYS)[number];

/** #/components/schemas/ReviewStepState/properties/step/enum */
export const REVIEW_STEP_KEYS = [
  "acquire_source",
  "build_experiment_environment",
  "activate_experiment_environment",
  "experiments",
] as const;
export type ReviewStepKey = (typeof REVIEW_STEP_KEYS)[number];

/** #/components/schemas/RunSummary/properties/operation/enum */
export const REE_RUN_OPERATIONS = [
  "initialize_ree",
  "acquire_source",
  "remove_source",
  "load_ree_bundle",
  "patch_ree_definition",
  "write_script",
  "suggest_scripts",
  "lint_scripts",
  "evaluate_reproducibility",
  "observe_hardware",
  "check_working_environment",
  "materialize_workspace",
  "build_experiment_environment",
  "generate_sbom",
  "cross_check_sbom",
  "activate_experiment_environment",
  "run_experiment",
  "seal_ree",
  "sign_ree",
  "review_acquire_source",
  "review_build_experiment_environment",
  "review_activate_experiment_environment",
  "review_run_experiment",
] as const;
export type ReeRunOperation = (typeof REE_RUN_OPERATIONS)[number];

/** #/components/schemas/ReeAudit/properties */
export const REE_AUDIT_KEYS = [
  "acquire_source",
  "evaluate_reproducibility",
  "observe_hardware",
  "check_working_environment",
  "build_experiment_environment",
  "generate_sbom",
  "cross_check_sbom",
  "activate_experiment_environment",
  "experiments",
] as const;
export type ReeAuditKey = (typeof REE_AUDIT_KEYS)[number];

/** #/components/schemas/ReeReceipts/properties */
export const REE_RECEIPT_KEYS = [
  "acquire_source",
  "evaluate_reproducibility",
  "observe_hardware",
  "check_working_environment",
  "build_experiment_environment",
  "generate_sbom",
  "cross_check_sbom",
  "activate_experiment_environment",
  "experiments",
] as const;
export type ReeReceiptKey = (typeof REE_RECEIPT_KEYS)[number];

/** #/components/schemas/ReeReceipts/properties */
export const RECEIPT_OPERATIONS = [
  "acquire_source",
  "evaluate_reproducibility",
  "observe_hardware",
  "check_working_environment",
  "build_experiment_environment",
  "generate_sbom",
  "cross_check_sbom",
  "activate_experiment_environment",
  "run_experiment",
] as const;
export type ReceiptOperation = (typeof RECEIPT_OPERATIONS)[number];

/** #/components/schemas/ScriptTarget/properties/kind/enum */
export const SCRIPT_KINDS = [
  "build_experiment_environment",
  "activate_experiment_environment",
  "experiment_run",
  "experiment_verify",
  "launch",
  "check_working_environment",
] as const;
export type ScriptKind = (typeof SCRIPT_KINDS)[number];

/** Each step key by its constant name. */
export const STEP = {
  ACQUIRE_SOURCE: "acquire_source",
  METADATA: "metadata",
  OBSERVE_HARDWARE: "observe_hardware",
  CHECK_WORKING_ENVIRONMENT: "check_working_environment",
  EVALUATE_REPRODUCIBILITY: "evaluate_reproducibility",
  BUILD_EXPERIMENT_ENVIRONMENT: "build_experiment_environment",
  GENERATE_SBOM: "generate_sbom",
  CROSS_CHECK_SBOM: "cross_check_sbom",
  ACTIVATE_EXPERIMENT_ENVIRONMENT: "activate_experiment_environment",
  EXPERIMENTS: "experiments",
  SEAL_REE: "seal_ree",
} as const satisfies Record<string, StepKey>;
