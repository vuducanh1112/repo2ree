import {
  AUTHORING_STEP_KEYS,
  type AuthoringProgress,
  type AuthoringStepKey,
  type AuthoringStepStatus,
} from "@core/ree/AuthoringProgress";

const LABELS: Readonly<Record<AuthoringStepKey, string>> = {
  acquire_source: "Source Acquisition",
  metadata: "Provide Metadata",
  observe_hardware: "Hardware BOM",
  evaluate_reproducibility: "Reproducibility Readiness",
  build_experiment_environment: "Build Experiment Environment",
  generate_sbom: "Generate SBOM",
  cross_check_sbom: "Cross-check SBOM",
  activate_experiment_environment: "Test Activation",
  experiments: "Experiments",
  seal_ree: "Seal",
};

const REQUIRES: Readonly<Partial<Record<AuthoringStepKey, readonly AuthoringStepKey[]>>> = {
  evaluate_reproducibility: ["acquire_source"],
  build_experiment_environment: ["acquire_source"],
  generate_sbom: ["build_experiment_environment"],
  cross_check_sbom: ["generate_sbom", "evaluate_reproducibility"],
  activate_experiment_environment: ["build_experiment_environment"],
  experiments: ["build_experiment_environment"],
};

export function authoringProgress(
  statuses: Partial<Record<AuthoringStepKey, AuthoringStepStatus>> = {},
  next?: AuthoringStepKey,
): AuthoringProgress {
  return {
    steps: AUTHORING_STEP_KEYS.map((key, index) => ({
      key,
      order: index + 1,
      label: LABELS[key],
      requires: REQUIRES[key] ?? [],
      status: statuses[key] ?? "blocked",
    })),
    next,
  };
}
