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
  // The scan targets the runtime the build recipe declares, which the backend
  // reads off the definition; the page names no artifact of its own.
  sbom: Record<string, never>;
  activation: ReeStepParamsByKey["activation"];
}

export type ReeStepRunParams<K extends ReeStepKey = ReeStepKey> = ReeStepRunParamsByKey[K];
