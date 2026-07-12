import type { ReeSpec } from "../../core/ree/ReeSpec";
import { REE_STEPS } from "../ree-steps/stepCatalog";

interface ManualArtifactCompletionPlan {
  reeSpecPatch?: Partial<ReeSpec>;
  lock?: boolean;
  successMessage: string;
}

interface ManualArtifactCompletionArgs {
  key: string;
  generatedSwhid?: string;
  generatedZenodoDoi?: string;
  generatedDataverseDoi?: string;
}

export function planManualArtifactCompletion({
  key,
  generatedSwhid,
  generatedZenodoDoi,
  generatedDataverseDoi,
}: ManualArtifactCompletionArgs): ManualArtifactCompletionPlan {
  if (key === "create") {
    return {
      lock: true,
      successMessage: "REE created — fields locked",
    };
  }

  if (key === "swh") {
    return {
      reeSpecPatch: { swhid: generatedSwhid || "" },
      successMessage: "Archived at Software Heritage — SWHID assigned",
    };
  }

  if (key === "zenodo") {
    return {
      reeSpecPatch: { zenodo_doi: generatedZenodoDoi || "" },
      successMessage: "Published on Zenodo — DOI assigned",
    };
  }

  if (key === "dataverse") {
    return {
      reeSpecPatch: { dataverse_doi: generatedDataverseDoi || "" },
      successMessage: "Dataset published on Dataverse — DOI assigned",
    };
  }

  const step = REE_STEPS.find((step) => step.key === key);
  return {
    successMessage: `${step?.label ?? key} completed`,
  };
}
