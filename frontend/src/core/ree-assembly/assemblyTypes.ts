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
  build: ReeAssemblyOperationParamsByKey["build"] & {
    build_runtime_script_path?: string;
  };
  hbom: ReeAssemblyOperationParamsByKey["hbom"];
  sbom: ReeAssemblyOperationParamsByKey["sbom"] & {
    produced_runtime_path?: string;
  };
  activation: ReeAssemblyOperationParamsByKey["activation"];
}

export type ReeAssemblyRunParams<K extends ReeAssemblyOperationKey = ReeAssemblyOperationKey> =
  ReeAssemblyRunParamsByKey[K];
