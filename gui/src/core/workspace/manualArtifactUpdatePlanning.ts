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

// Deposit steps (Software Heritage, Zenodo, Dataverse) patch nothing here. A
// deposit identifier names a *deposit of* a sealed REE, not the REE itself, so
// it is recorded as an archive-binding attestation server-side rather than
// written onto the spec. These branches used to synthesize identifiers locally,
// which made the UI claim an archival relationship that never existed.
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
