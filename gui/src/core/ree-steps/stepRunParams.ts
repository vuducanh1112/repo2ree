export type {
  ReeStepKey,
  ReeStepParams,
  ReeStepParamsByKey,
} from "./ReeStepParams";

import type { ReeStepKey, ReeStepParamsByKey } from "./ReeStepParams";

export interface ReeStepRunParamsByKey {
  evaluate_reproducibility: ReeStepParamsByKey["evaluate_reproducibility"];
  // The build always runs the reserved build script; it takes no parameters.
  build_experiment_environment: Record<string, never>;
  observe_hardware: ReeStepParamsByKey["observe_hardware"];
  // The scan targets the runtime the build recipe declares, which the backend
  // reads off the definition; the page names no artifact of its own.
  generate_sbom: Record<string, never>;
  activate_experiment_environment: ReeStepParamsByKey["activate_experiment_environment"];
}

export type ReeStepRunParams<K extends ReeStepKey = ReeStepKey> = ReeStepRunParamsByKey[K];
