import { REE_ASSEMBLY_STEPS } from "../ree-assembly/assemblyCatalog";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";

interface ManualArtifactCompletionPlan {
  reePatch?: Partial<ReeEditorViewModel>;
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

  const assemblyStep = REE_ASSEMBLY_STEPS.find((assemblyStep) => assemblyStep.key === key);
  return {
    successMessage: `${assemblyStep?.label ?? key} completed`,
  };
}
