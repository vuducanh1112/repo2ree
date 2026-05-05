export type {
  AutomationStepKey,
  AutomationStepParams,
  AutomationStepParamsByKey,
} from "../../domain/workflow/AutomationStepTypes";

import type {
  AutomationStepKey,
  AutomationStepParamsByKey,
} from "../../domain/workflow/AutomationStepTypes";

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
