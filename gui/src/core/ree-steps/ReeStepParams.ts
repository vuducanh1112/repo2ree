export type ReeStepKey =
  | "evaluate"
  | "build_experiment_environment"
  | "hbom"
  | "sbom"
  | "activation";

export interface ReeStepParamsByKey {
  evaluate: {
    strict: boolean;
  };
  build_experiment_environment: Record<string, never>;
  hbom: Record<string, never>;
  sbom: Record<string, never>;
  activation: Record<string, never>;
}

export type ReeStepParams = {
  [K in ReeStepKey]: ReeStepParamsByKey[K];
};
