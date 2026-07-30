export type {
  ReeStepKey,
  ReeStepParams,
  ReeStepParamsByKey,
} from "./ReeStepParams";

import type { ReeStepKey, ReeStepParamsByKey } from "./ReeStepParams";

export interface ReeStepRunParamsByKey {
  evaluate: ReeStepParamsByKey["evaluate"];
  // The build always runs the reserved build script; it takes no parameters.
  build: Record<string, never>;
  hbom: ReeStepParamsByKey["hbom"];
  // The catalog declares no authored sbom params; the runtime path is wired
  // in by the page from the selected build artifact.
  sbom: {
    producedRuntimePath?: string;
  };
  activation: ReeStepParamsByKey["activation"];
}

export type ReeStepRunParams<K extends ReeStepKey = ReeStepKey> = ReeStepRunParamsByKey[K];
