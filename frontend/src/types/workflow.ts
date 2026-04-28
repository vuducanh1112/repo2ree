export type WorkflowServiceKey = "evaluate" | "build" | "hbom" | "sbom" | "activation";

export interface WorkflowServiceParamsByKey {
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

export type WorkflowServiceParams = {
  [K in WorkflowServiceKey]: WorkflowServiceParamsByKey[K];
};

export interface WorkflowServiceRunParamsByKey {
  evaluate: WorkflowServiceParamsByKey["evaluate"];
  build: WorkflowServiceParamsByKey["build"] & {
    build_runtime_script_path?: string;
    produced_runtime_path?: string;
    _expectedOutput?: string;
  };
  hbom: WorkflowServiceParamsByKey["hbom"];
  sbom: WorkflowServiceParamsByKey["sbom"] & {
    produced_runtime_path?: string;
  };
  activation: WorkflowServiceParamsByKey["activation"];
}

export type WorkflowServiceRunParams<K extends WorkflowServiceKey = WorkflowServiceKey> =
  WorkflowServiceRunParamsByKey[K];
