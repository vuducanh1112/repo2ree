import type { StepKey } from "@core/generated/vocabulary";

// The steps a page runs from its dock, each with the parameters it takes.
export const REE_STEP_KEYS = [
  "evaluate_reproducibility",
  "build_experiment_environment",
  "observe_hardware",
  "generate_sbom",
  "activate_experiment_environment",
] as const satisfies readonly StepKey[];

export type ReeStepKey = (typeof REE_STEP_KEYS)[number];

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
