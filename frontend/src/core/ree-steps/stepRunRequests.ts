import type { ReeSpec } from "../ree/ReeSpec";
import type { ReeStepKey, ReeStepRunParamsByKey } from "./stepRunParams";
import type { GenericReeStepParams } from "./stepTypes";

type StepRee = Pick<ReeSpec, "runtime">;

type StepRequestParamValue = string | boolean | number | null | undefined;

interface ReeStepRunRequestByKey {
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

type ReeStepRunRequest<K extends ReeStepKey = ReeStepKey> = ReeStepRunRequestByKey[K];

export function buildEvaluateStepRunRequest(
  params: ReeStepRunParamsByKey["evaluate"],
): ReeStepRunRequestByKey["evaluate"] {
  return {
    scriptKey: "evaluate",
    params: {
      strict: Boolean(params.strict),
    },
  };
}

export function buildBuildStepRunRequest(
  _params: ReeStepRunParamsByKey["build"],
  _ree: StepRee,
): ReeStepRunRequestByKey["build"] {
  // The build always runs the reserved build script; there is nothing to send.
  return {
    scriptKey: "build",
    params: {},
  };
}

function buildHbomStepRunRequest(
  _params: ReeStepRunParamsByKey["hbom"],
): ReeStepRunRequestByKey["hbom"] {
  return {
    scriptKey: "hbom",
    params: {},
  };
}

export function buildSbomStepRunRequest(
  params: ReeStepRunParamsByKey["sbom"],
  ree: StepRee,
): ReeStepRunRequestByKey["sbom"] {
  return {
    scriptKey: "sbom",
    params: {
      produced_runtime_path: String(params.produced_runtime_path ?? ree.runtime ?? ""),
    },
  };
}

export function buildActivationStepRunRequest(
  _params: ReeStepRunParamsByKey["activation"],
  _ree: StepRee,
): ReeStepRunRequestByKey["activation"] {
  return {
    scriptKey: "activation",
    params: {},
  };
}

export function buildStepRunRequest<K extends ReeStepKey>(
  key: K,
  params: ReeStepRunParamsByKey[K],
  ree: StepRee,
): ReeStepRunRequest<K> {
  switch (key) {
    case "evaluate":
      return buildEvaluateStepRunRequest(
        params as ReeStepRunParamsByKey["evaluate"],
      ) as ReeStepRunRequest<K>;
    case "build":
      return buildBuildStepRunRequest(
        params as ReeStepRunParamsByKey["build"],
        ree,
      ) as ReeStepRunRequest<K>;
    case "hbom":
      return buildHbomStepRunRequest(
        params as ReeStepRunParamsByKey["hbom"],
      ) as ReeStepRunRequest<K>;
    case "sbom":
      return buildSbomStepRunRequest(
        params as ReeStepRunParamsByKey["sbom"],
        ree,
      ) as ReeStepRunRequest<K>;
    case "activation":
      return buildActivationStepRunRequest(
        params as ReeStepRunParamsByKey["activation"],
        ree,
      ) as ReeStepRunRequest<K>;
  }
}

export function buildStepRunParams(
  key: string,
  params: GenericReeStepParams,
  ree: StepRee,
): Record<string, StepRequestParamValue> {
  // Delegate to the single typed dispatcher so the per-key request shapes are
  // defined in exactly one place; keys outside the known set pass through.
  if (!isReeStepKey(key)) {
    return params;
  }
  return buildStepRunRequest(key, params as ReeStepRunParamsByKey[typeof key], ree).params;
}

const REE_STEP_KEYS: readonly ReeStepKey[] = ["evaluate", "build", "hbom", "sbom", "activation"];

function isReeStepKey(key: string): key is ReeStepKey {
  return (REE_STEP_KEYS as readonly string[]).includes(key);
}
