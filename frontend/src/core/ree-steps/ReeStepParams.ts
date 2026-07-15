export type ReeStepKey = "evaluate" | "build" | "hbom" | "sbom" | "activation";

export interface ReeStepParamsByKey {
  evaluate: {
    strict: boolean;
  };
  build: Record<string, never>;
  hbom: Record<string, never>;
  sbom: Record<string, never>;
  activation: Record<string, never>;
}

export type ReeStepParams = {
  [K in ReeStepKey]: ReeStepParamsByKey[K];
};
