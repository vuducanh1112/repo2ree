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

export interface AutomationStepRunParamsByKey {
  evaluate: AutomationStepParamsByKey["evaluate"];
  build: AutomationStepParamsByKey["build"] & {
    build_runtime_script_path?: string;
    produced_runtime_path?: string;
    _expectedOutput?: string;
  };
  hbom: AutomationStepParamsByKey["hbom"];
  sbom: AutomationStepParamsByKey["sbom"] & {
    produced_runtime_path?: string;
  };
  activation: AutomationStepParamsByKey["activation"];
}

export type AutomationStepRunParams<K extends AutomationStepKey = AutomationStepKey> =
  AutomationStepRunParamsByKey[K];
