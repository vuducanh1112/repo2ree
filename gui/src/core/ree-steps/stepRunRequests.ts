import type { ReeSpec } from "../ree/ReeSpec";
import { isReeStepKey } from "./stepPolicies";
import type { ReeStepKey, ReeStepRunParamsByKey } from "./stepRunParams";
import type { GenericReeStepParams } from "./stepTypes";

type StepRee = Pick<ReeSpec, "experimentEnvironmentPath">;

type StepRequestParamValue = string | boolean | number | null | undefined;

interface ReeStepRunRequestByKey {
  evaluate_reproducibility: {
    scriptKey: "evaluate_reproducibility";
    params: {
      strict: boolean;
      idempotencyKey?: string;
    };
  };
  build_experiment_environment: {
    scriptKey: "build_experiment_environment";
    params: {
      idempotencyKey?: string;
    };
  };
  observe_hardware: {
    scriptKey: "observe_hardware";
    params: {
      idempotencyKey?: string;
    };
  };
  generate_sbom: {
    scriptKey: "generate_sbom";
    params: {
      idempotencyKey?: string;
    };
  };
  activate_experiment_environment: {
    scriptKey: "activate_experiment_environment";
    params: {
      idempotencyKey?: string;
    };
  };
}

type ReeStepRunRequest<K extends ReeStepKey = ReeStepKey> = ReeStepRunRequestByKey[K];

export function buildEvaluateStepRunRequest(
  params: ReeStepRunParamsByKey["evaluate_reproducibility"],
): ReeStepRunRequestByKey["evaluate_reproducibility"] {
  return {
    scriptKey: "evaluate_reproducibility",
    params: {
      strict: Boolean(params.strict),
    },
  };
}

export function buildBuildStepRunRequest(
  _params: ReeStepRunParamsByKey["build_experiment_environment"],
  _ree: StepRee,
): ReeStepRunRequestByKey["build_experiment_environment"] {
  // The build always runs the reserved build script; there is nothing to send.
  return {
    scriptKey: "build_experiment_environment",
    params: {},
  };
}

function buildHbomStepRunRequest(
  _params: ReeStepRunParamsByKey["observe_hardware"],
): ReeStepRunRequestByKey["observe_hardware"] {
  return {
    scriptKey: "observe_hardware",
    params: {},
  };
}

export function buildSbomStepRunRequest(
  _params: ReeStepRunParamsByKey["generate_sbom"],
  _ree: StepRee,
): ReeStepRunRequestByKey["generate_sbom"] {
  // The scan targets the runtime the build recipe declares; there is nothing
  // to send that the REE does not already hold.
  return {
    scriptKey: "generate_sbom",
    params: {},
  };
}

export function buildActivationStepRunRequest(
  _params: ReeStepRunParamsByKey["activate_experiment_environment"],
  _ree: StepRee,
): ReeStepRunRequestByKey["activate_experiment_environment"] {
  return {
    scriptKey: "activate_experiment_environment",
    params: {},
  };
}

export function buildStepRunRequest<K extends ReeStepKey>(
  key: K,
  params: ReeStepRunParamsByKey[K],
  ree: StepRee,
): ReeStepRunRequest<K> {
  switch (key) {
    case "evaluate_reproducibility":
      return buildEvaluateStepRunRequest(
        params as ReeStepRunParamsByKey["evaluate_reproducibility"],
      ) as ReeStepRunRequest<K>;
    case "build_experiment_environment":
      return buildBuildStepRunRequest(
        params as ReeStepRunParamsByKey["build_experiment_environment"],
        ree,
      ) as ReeStepRunRequest<K>;
    case "observe_hardware":
      return buildHbomStepRunRequest(
        params as ReeStepRunParamsByKey["observe_hardware"],
      ) as ReeStepRunRequest<K>;
    case "generate_sbom":
      return buildSbomStepRunRequest(
        params as ReeStepRunParamsByKey["generate_sbom"],
        ree,
      ) as ReeStepRunRequest<K>;
    case "activate_experiment_environment":
      return buildActivationStepRunRequest(
        params as ReeStepRunParamsByKey["activate_experiment_environment"],
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
