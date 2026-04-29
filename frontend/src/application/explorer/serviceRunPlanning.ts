import { PAGE } from "../../constants/pages";
import { SERVICES } from "../../constants/services";
import type { Ree, WorkflowServiceKey } from "../../types";
import type { GenericServiceParams } from "../../types/services";

type ServiceRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

export function buildRemoteServiceRunParams(
  key: string,
  params: GenericServiceParams,
  ree: Ree,
): GenericServiceParams {
  if (key !== "activation") {
    return params;
  }

  return {
    ...params,
    activation_script: ree.activation_script,
  };
}

export function isTerminalServiceRunFailure(status: ServiceRunStatus): boolean {
  return status === "failed" || status === "canceled";
}

export function shouldRefreshWorkspaceAfterServiceRun(key: string): boolean {
  return key === "build" || key === "sbom" || key === "hbom";
}

export function deriveServiceRunLevel(
  key: string,
  currentLevel: number,
  evaluatedLevel: number,
): number {
  return key === PAGE.EVALUATE ? evaluatedLevel : currentLevel;
}

export function isWorkflowServiceRunKey(key: string): key is WorkflowServiceKey {
  return (
    key === "evaluate" ||
    key === "hbom" ||
    key === "build" ||
    key === "sbom" ||
    key === "activation"
  );
}

interface ServiceRunCompletionPlan {
  actionState: "done";
  badge: true;
  timestamp: string;
  shouldRefreshWorkspace: boolean;
}

interface ServiceRunFailurePlan extends ServiceRunCompletionPlan {
  errorMessage: string;
}

interface ServiceRunSuccessPlan extends ServiceRunCompletionPlan {
  successMessage?: string;
  reePatch?: Partial<Ree>;
  lock?: boolean;
}

interface NonWorkflowCompletionArgs {
  key: string;
  generatedSwhid?: string;
  generatedZenodoDoi?: string;
  generatedDataverseDoi?: string;
}

export function planServiceRunCompletion(key: string, timestamp: string): ServiceRunCompletionPlan {
  return {
    actionState: "done",
    badge: true,
    timestamp,
    shouldRefreshWorkspace: shouldRefreshWorkspaceAfterServiceRun(key),
  };
}

export function planTerminalServiceRunFailure(
  key: string,
  status: Extract<ServiceRunStatus, "failed" | "canceled">,
  timestamp: string,
): ServiceRunFailurePlan {
  return {
    ...planServiceRunCompletion(key, timestamp),
    errorMessage: `${key} ${status}`,
  };
}

export function planNonWorkflowServiceRunSuccess(
  args: NonWorkflowCompletionArgs & { timestamp: string },
): ServiceRunSuccessPlan {
  if (args.key === "create") {
    return {
      ...planServiceRunCompletion(args.key, args.timestamp),
      lock: true,
      successMessage: "REE created — fields locked",
    };
  }

  if (args.key === "swh") {
    return {
      ...planServiceRunCompletion(args.key, args.timestamp),
      reePatch: { swhid: args.generatedSwhid || "" },
      successMessage: "Archived at Software Heritage — SWHID assigned",
    };
  }

  if (args.key === "zenodo") {
    return {
      ...planServiceRunCompletion(args.key, args.timestamp),
      reePatch: { zenodo_doi: args.generatedZenodoDoi || "" },
      successMessage: "Published on Zenodo — DOI assigned",
    };
  }

  if (args.key === "dataverse") {
    return {
      ...planServiceRunCompletion(args.key, args.timestamp),
      reePatch: { dataverse_doi: args.generatedDataverseDoi || "" },
      successMessage: "Dataset published on Dataverse — DOI assigned",
    };
  }

  const service = SERVICES.find((candidate) => candidate.key === args.key);
  return {
    ...planServiceRunCompletion(args.key, args.timestamp),
    successMessage: `${service?.label ?? args.key} completed`,
  };
}
