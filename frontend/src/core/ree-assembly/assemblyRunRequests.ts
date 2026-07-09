import type { ReeSpec } from "../ree/ReeSpec";
import type { GenericReeAssemblyParams } from "./assemblyStepTypes";
import type { ReeAssemblyOperationKey, ReeAssemblyRunParamsByKey } from "./assemblyTypes";

type AssemblyRee = Pick<ReeSpec, "runtime">;

type AssemblyRequestParamValue = string | boolean | number | null | undefined;

interface ReeAssemblyRunRequestByKey {
  evaluate: {
    scriptKey: "evaluate";
    params: {
      strict: boolean;
      idempotencyKey?: string;
    };
  };
  build: {
    scriptKey: "build";
    params: {
      idempotencyKey?: string;
    };
  };
  hbom: {
    scriptKey: "hbom";
    params: {
      idempotencyKey?: string;
    };
  };
  sbom: {
    scriptKey: "sbom";
    params: {
      produced_runtime_path: string;
      idempotencyKey?: string;
    };
  };
  activation: {
    scriptKey: "activation";
    params: {
      idempotencyKey?: string;
    };
  };
}

type ReeAssemblyRunRequest<K extends ReeAssemblyOperationKey = ReeAssemblyOperationKey> =
  ReeAssemblyRunRequestByKey[K];

export function buildEvaluateAssemblyRunRequest(
  params: ReeAssemblyRunParamsByKey["evaluate"],
): ReeAssemblyRunRequestByKey["evaluate"] {
  return {
    scriptKey: "evaluate",
    params: {
      strict: Boolean(params.strict),
    },
  };
}

export function buildBuildAssemblyRunRequest(
  _params: ReeAssemblyRunParamsByKey["build"],
  _ree: AssemblyRee,
): ReeAssemblyRunRequestByKey["build"] {
  // The build always runs the reserved build script; there is nothing to send.
  return {
    scriptKey: "build",
    params: {},
  };
}

function buildHbomAssemblyRunRequest(
  _params: ReeAssemblyRunParamsByKey["hbom"],
): ReeAssemblyRunRequestByKey["hbom"] {
  return {
    scriptKey: "hbom",
    params: {},
  };
}

export function buildSbomAssemblyRunRequest(
  params: ReeAssemblyRunParamsByKey["sbom"],
  ree: AssemblyRee,
): ReeAssemblyRunRequestByKey["sbom"] {
  return {
    scriptKey: "sbom",
    params: {
      produced_runtime_path: String(params.produced_runtime_path ?? ree.runtime ?? ""),
    },
  };
}

export function buildActivationAssemblyRunRequest(
  _params: ReeAssemblyRunParamsByKey["activation"],
  _ree: AssemblyRee,
): ReeAssemblyRunRequestByKey["activation"] {
  return {
    scriptKey: "activation",
    params: {},
  };
}

export function buildAssemblyRunRequest<K extends ReeAssemblyOperationKey>(
  key: K,
  params: ReeAssemblyRunParamsByKey[K],
  ree: AssemblyRee,
): ReeAssemblyRunRequest<K> {
  switch (key) {
    case "evaluate":
      return buildEvaluateAssemblyRunRequest(
        params as ReeAssemblyRunParamsByKey["evaluate"],
      ) as ReeAssemblyRunRequest<K>;
    case "build":
      return buildBuildAssemblyRunRequest(
        params as ReeAssemblyRunParamsByKey["build"],
        ree,
      ) as ReeAssemblyRunRequest<K>;
    case "hbom":
      return buildHbomAssemblyRunRequest(
        params as ReeAssemblyRunParamsByKey["hbom"],
      ) as ReeAssemblyRunRequest<K>;
    case "sbom":
      return buildSbomAssemblyRunRequest(
        params as ReeAssemblyRunParamsByKey["sbom"],
        ree,
      ) as ReeAssemblyRunRequest<K>;
    case "activation":
      return buildActivationAssemblyRunRequest(
        params as ReeAssemblyRunParamsByKey["activation"],
        ree,
      ) as ReeAssemblyRunRequest<K>;
  }
}

export function buildAssemblyRunParams(
  key: string,
  params: GenericReeAssemblyParams,
  ree: AssemblyRee,
): Record<string, AssemblyRequestParamValue> {
  // Delegate to the single typed dispatcher so the per-key request shapes are
  // defined in exactly one place; keys outside the known set pass through.
  if (!isReeAssemblyOperationKey(key)) {
    return params;
  }
  return buildAssemblyRunRequest(key, params as ReeAssemblyRunParamsByKey[typeof key], ree).params;
}

const REE_ASSEMBLY_OPERATION_KEYS: readonly ReeAssemblyOperationKey[] = [
  "evaluate",
  "build",
  "hbom",
  "sbom",
  "activation",
];

function isReeAssemblyOperationKey(key: string): key is ReeAssemblyOperationKey {
  return (REE_ASSEMBLY_OPERATION_KEYS as readonly string[]).includes(key);
}
