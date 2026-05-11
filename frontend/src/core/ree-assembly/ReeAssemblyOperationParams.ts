export type ReeAssemblyOperationKey = "evaluate" | "build" | "hbom" | "sbom" | "activation";

export interface ReeAssemblyOperationParamsByKey {
  evaluate: {
    strict: boolean;
    swhid_check: boolean;
  };
  build: Record<string, never>;
  hbom: Record<string, never>;
  sbom: {
    format: string;
  };
  activation: {
    timeout: string;
    verbose: boolean;
  };
}

export type ReeAssemblyOperationParams = {
  [K in ReeAssemblyOperationKey]: ReeAssemblyOperationParamsByKey[K];
};
