export type {
  ReeAssemblyOperationKey,
  ReeAssemblyOperationParams,
  ReeAssemblyOperationParamsByKey,
} from "./ReeAssemblyOperationParams";

import type {
  ReeAssemblyOperationKey,
  ReeAssemblyOperationParamsByKey,
} from "./ReeAssemblyOperationParams";

export interface ReeAssemblyRunParamsByKey {
  evaluate: ReeAssemblyOperationParamsByKey["evaluate"];
  // The build always runs the reserved build script; it takes no parameters.
  build: Record<string, never>;
  hbom: ReeAssemblyOperationParamsByKey["hbom"];
  sbom: ReeAssemblyOperationParamsByKey["sbom"] & {
    produced_runtime_path?: string;
  };
  activation: ReeAssemblyOperationParamsByKey["activation"];
}

export type ReeAssemblyRunParams<K extends ReeAssemblyOperationKey = ReeAssemblyOperationKey> =
  ReeAssemblyRunParamsByKey[K];
