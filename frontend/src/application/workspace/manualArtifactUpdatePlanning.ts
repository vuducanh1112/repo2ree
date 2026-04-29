import { AUTOMATION_STEPS } from "../../constants/workflowSteps";
import type { Ree } from "../../types";

interface NonWorkflowCompletionPlan {
  reePatch?: Partial<Ree>;
  lock?: boolean;
  successMessage: string;
}

interface NonWorkflowCompletionArgs {
  key: string;
  generatedSwhid?: string;
  generatedZenodoDoi?: string;
  generatedDataverseDoi?: string;
}

export function planNonWorkflowCompletion({
  key,
  generatedSwhid,
  generatedZenodoDoi,
  generatedDataverseDoi,
}: NonWorkflowCompletionArgs): NonWorkflowCompletionPlan {
  if (key === "create") {
    return {
      lock: true,
      successMessage: "REE created — fields locked",
    };
  }

  if (key === "swh") {
    return {
      reePatch: { swhid: generatedSwhid || "" },
      successMessage: "Archived at Software Heritage — SWHID assigned",
    };
  }

  if (key === "zenodo") {
    return {
      reePatch: { zenodo_doi: generatedZenodoDoi || "" },
      successMessage: "Published on Zenodo — DOI assigned",
    };
  }

  if (key === "dataverse") {
    return {
      reePatch: { dataverse_doi: generatedDataverseDoi || "" },
      successMessage: "Dataset published on Dataverse — DOI assigned",
    };
  }

  const svc = AUTOMATION_STEPS.find((service) => service.key === key);
  return {
    successMessage: `${svc?.label ?? key} completed`,
  };
}
