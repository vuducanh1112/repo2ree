export type ReeStepKey =
  | "evaluate_reproducibility"
  | "build_experiment_environment"
  | "observe_hardware"
  | "generate_sbom"
  | "activate_experiment_environment";

export interface ReeStepParamsByKey {
  evaluate_reproducibility: {
    strict: boolean;
  };
  build_experiment_environment: Record<string, never>;
  observe_hardware: Record<string, never>;
  generate_sbom: Record<string, never>;
  activate_experiment_environment: Record<string, never>;
}

export type ReeStepParams = {
  [K in ReeStepKey]: ReeStepParamsByKey[K];
};
