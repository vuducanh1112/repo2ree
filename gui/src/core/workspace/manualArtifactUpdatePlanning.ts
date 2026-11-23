import type { ReeSpec } from "../../core/ree/ReeSpec";
import { REE_STEPS } from "../ree-steps/stepCatalog";

interface ManualArtifactCompletionPlan {
  reeSpecPatch?: Partial<ReeSpec>;
  lock?: boolean;
  successMessage: string;
}

interface ManualArtifactCompletionArgs {
  key: string;
}

export function planManualArtifactCompletion({
  key,
}: ManualArtifactCompletionArgs): ManualArtifactCompletionPlan {
  if (key === "create") {
    return {
      lock: true,
      successMessage: "REE created — fields locked",
    };
  }

  const step = REE_STEPS.find((step) => step.key === key);
  return {
    successMessage: `${step?.label ?? key} completed`,
  };
}
