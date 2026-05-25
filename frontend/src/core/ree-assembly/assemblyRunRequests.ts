import type { ReeSpec } from "../ree/ReeSpec";
import type { GenericReeAssemblyParams } from "./assemblyStepTypes";
import type { ReeAssemblyOperationKey, ReeAssemblyRunParamsByKey } from "./assemblyTypes";

type AssemblyRee = Pick<ReeSpec, "build_runtime_script" | "runtime" | "activation_script">;

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
      build_runtime_script_path: string;
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
      activation_script_path: string;
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
  params: ReeAssemblyRunParamsByKey["build"],
  ree: AssemblyRee,
): ReeAssemblyRunRequestByKey["build"] {
  return {
    scriptKey: "build",
    params: {
      build_runtime_script_path: String(
        params.build_runtime_script_path ?? ree.build_runtime_script ?? "",
      ),
    },
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
  params: ReeAssemblyRunParamsByKey["activation"],
  ree: AssemblyRee,
): ReeAssemblyRunRequestByKey["activation"] {
  void params;
  return {
    scriptKey: "activation",
    params: {
      activation_script_path: String(ree.activation_script ?? ""),
    },
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
  if (key === "evaluate") {
    return buildEvaluateAssemblyRunRequest(params as ReeAssemblyRunParamsByKey["evaluate"]).params;
  }
  if (key === "build") {
    return buildBuildAssemblyRunRequest(params as ReeAssemblyRunParamsByKey["build"], ree).params;
  }
  if (key === "hbom") {
    return buildHbomAssemblyRunRequest(params as ReeAssemblyRunParamsByKey["hbom"]).params;
  }
  if (key === "sbom") {
    return buildSbomAssemblyRunRequest(params as ReeAssemblyRunParamsByKey["sbom"], ree).params;
  }
  if (key === "activation") {
    return buildActivationAssemblyRunRequest(params as ReeAssemblyRunParamsByKey["activation"], ree)
      .params;
  }
  return params;
}
