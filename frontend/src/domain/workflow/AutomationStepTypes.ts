export type AutomationStepKey = "evaluate" | "build" | "hbom" | "sbom" | "activation";

export interface AutomationStepParamsByKey {
  evaluate: {
    strict: boolean;
    swhid_check: boolean;
  };
  build: {
    no_cache: boolean;
    platform: string;
  };
  hbom: Record<string, never>;
  sbom: {
    format: string;
  };
  activation: {
    timeout: string;
    verbose: boolean;
  };
}

export type AutomationStepParams = {
  [K in AutomationStepKey]: AutomationStepParamsByKey[K];
};
