export type {
  ReeStepKey,
  ReeStepParams,
  ReeStepParamsByKey,
} from "./ReeStepParams";

import type { ReeStepKey, ReeStepParamsByKey } from "./ReeStepParams";

export interface ReeStepRunParamsByKey {
  evaluate_reproducibility: ReeStepParamsByKey["evaluate_reproducibility"];
  build_experiment_environment: Record<string, never>;
  observe_hardware: ReeStepParamsByKey["observe_hardware"];
  generate_sbom: Record<string, never>;
  activate_experiment_environment: ReeStepParamsByKey["activate_experiment_environment"];
}

export type ReeStepRunParams<K extends ReeStepKey = ReeStepKey> = ReeStepRunParamsByKey[K];
