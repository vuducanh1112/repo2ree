import {
  AUTHORING_STEP_KEYS,
  type AuthoringProgress,
  type AuthoringStepKey,
  type AuthoringStepStatus,
} from "@core/ree/AuthoringProgress";

const LABELS: Readonly<Record<AuthoringStepKey, string>> = {
  source: "Source Acquisition",
  metadata: "Provide Metadata",
  hbom: "Hardware BOM",
  evaluate: "Reproducibility Readiness",
  // biome-ignore lint/style/useNamingConvention: an authoring step key, as the REE names it
  build_experiment_environment: "Build Experiment Environment",
  sbom: "Generate SBOM",
  crosscheck: "Cross-check SBOM",
  activation: "Test Activation",
  experiments: "Experiments",
  seal: "Seal",
};

const REQUIRES: Readonly<Partial<Record<AuthoringStepKey, readonly AuthoringStepKey[]>>> = {
  evaluate: ["source"],
  // biome-ignore lint/style/useNamingConvention: an authoring step key, as the REE names it
  build_experiment_environment: ["source"],
  sbom: ["build_experiment_environment"],
  crosscheck: ["sbom", "evaluate"],
  activation: ["build_experiment_environment"],
  experiments: ["build_experiment_environment"],
};

/** The REE's word on its steps, as the document ships it: those not named are blocked. */
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
