import type { ReeViewState } from "../../domain/ree/ReeViewState";
import type { GenericWorkflowParams } from "./WorkflowStepTypes";
import type { AutomationStepKey, AutomationStepRunParamsByKey } from "./WorkflowTypes";

type WorkflowRequestParamValue = string | boolean | number | null | undefined;

interface WorkflowRunRequestByKey {
  evaluate: {
    scriptKey: "evaluate";
    params: {
      strict: boolean;
      swhid_check: boolean;
      idempotencyKey?: string;
    };
  };
  build: {
    scriptKey: "build";
    params: {
      build_runtime_script_path: string;
      produced_runtime_path: string;
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

type WorkflowRunRequest<K extends AutomationStepKey = AutomationStepKey> =
  WorkflowRunRequestByKey[K];

export function buildEvaluateWorkflowRequest(
  params: AutomationStepRunParamsByKey["evaluate"],
): WorkflowRunRequestByKey["evaluate"] {
  return {
    scriptKey: "evaluate",
    params: {
      strict: Boolean(params.strict),
      swhid_check: Boolean(params.swhid_check),
    },
  };
}

export function buildBuildWorkflowRequest(
  params: AutomationStepRunParamsByKey["build"],
  ree: ReeViewState,
): WorkflowRunRequestByKey["build"] {
  return {
    scriptKey: "build",
    params: {
      build_runtime_script_path: String(
        params.build_runtime_script_path ?? ree.build_runtime_script ?? "",
      ),
      produced_runtime_path: String(
        params.produced_runtime_path ?? ree.runtime ?? params._expectedOutput ?? "",
      ),
    },
  };
}

function buildHbomWorkflowRequest(
  _params: AutomationStepRunParamsByKey["hbom"],
): WorkflowRunRequestByKey["hbom"] {
  return {
    scriptKey: "hbom",
    params: {},
  };
}

export function buildSbomWorkflowRequest(
  params: AutomationStepRunParamsByKey["sbom"],
  ree: ReeViewState,
): WorkflowRunRequestByKey["sbom"] {
  return {
    scriptKey: "sbom",
    params: {
      produced_runtime_path: String(params.produced_runtime_path ?? ree.runtime ?? ""),
    },
  };
}

export function buildActivationWorkflowRequest(
  params: AutomationStepRunParamsByKey["activation"],
  ree: ReeViewState,
): WorkflowRunRequestByKey["activation"] {
  void params;
  return {
    scriptKey: "activation",
    params: {
      activation_script_path: String(ree.activation_script ?? ""),
    },
  };
}

export function buildWorkflowRunRequest<K extends AutomationStepKey>(
  key: K,
  params: AutomationStepRunParamsByKey[K],
  ree: ReeViewState,
): WorkflowRunRequest<K> {
  switch (key) {
    case "evaluate":
      return buildEvaluateWorkflowRequest(
        params as AutomationStepRunParamsByKey["evaluate"],
      ) as WorkflowRunRequest<K>;
    case "build":
      return buildBuildWorkflowRequest(
        params as AutomationStepRunParamsByKey["build"],
        ree,
      ) as WorkflowRunRequest<K>;
    case "hbom":
      return buildHbomWorkflowRequest(
        params as AutomationStepRunParamsByKey["hbom"],
      ) as WorkflowRunRequest<K>;
    case "sbom":
      return buildSbomWorkflowRequest(
        params as AutomationStepRunParamsByKey["sbom"],
        ree,
      ) as WorkflowRunRequest<K>;
    case "activation":
      return buildActivationWorkflowRequest(
        params as AutomationStepRunParamsByKey["activation"],
        ree,
      ) as WorkflowRunRequest<K>;
  }
}

export function buildWorkflowRunParams(
  key: string,
  params: GenericWorkflowParams,
  ree: ReeViewState,
): Record<string, WorkflowRequestParamValue> {
  if (key === "evaluate") {
    return buildEvaluateWorkflowRequest(params as AutomationStepRunParamsByKey["evaluate"]).params;
  }
  if (key === "build") {
    return buildBuildWorkflowRequest(params as AutomationStepRunParamsByKey["build"], ree).params;
  }
  if (key === "hbom") {
    return buildHbomWorkflowRequest(params as AutomationStepRunParamsByKey["hbom"]).params;
  }
  if (key === "sbom") {
    return buildSbomWorkflowRequest(params as AutomationStepRunParamsByKey["sbom"], ree).params;
  }
  if (key === "activation") {
    return buildActivationWorkflowRequest(params as AutomationStepRunParamsByKey["activation"], ree)
      .params;
  }
  return params;
}
