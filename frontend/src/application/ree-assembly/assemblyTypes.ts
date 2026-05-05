export type {
  AutomationStepKey as ReeAssemblyOperationKey,
  AutomationStepParams as ReeAssemblyOperationParams,
  AutomationStepParamsByKey as ReeAssemblyOperationParamsByKey,
} from "../../domain/workflow/AutomationStepTypes";

import type {
  AutomationStepKey,
  AutomationStepParamsByKey,
} from "../../domain/workflow/AutomationStepTypes";

export interface ReeAssemblyRunParamsByKey {
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

export type ReeAssemblyRunParams<K extends AutomationStepKey = AutomationStepKey> =
  ReeAssemblyRunParamsByKey[K];
