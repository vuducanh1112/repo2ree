import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import type { ReeSpec } from "../ree/ReeSpec";
import { SBOM_ARTIFACT_PATH } from "./sbomUiState";
import type { ReeStepKey } from "./stepRunParams";
import type { GenericReeStepParams } from "./stepTypes";

interface PersistedFilePlan {
  path: string;
  content: string;
}

interface BuildEffectPlan {
  persistedFile?: PersistedFilePlan;
  reeSpecPatch?: Partial<ReeSpec>;
  artifactStatusPatch?: Partial<ArtifactStatus>;
  errorMessage?: string;
  successMessage: string;
}

interface SbomEffectPlan {
  persistedFile?: PersistedFilePlan;
  reeSpecPatch: Partial<ReeSpec>;
  successMessage: string;
}

interface HbomEffectPlan {
  successMessage: string;
}

interface EvaluateEffectPlan {
  evaluationStatePatch: Partial<EvaluationState>;
  successMessage: string;
}

interface ActivationEffectPlan {
  successMessage: string;
}

interface StepServiceEffectPlan {
  persistedFile?: PersistedFilePlan;
  reeSpecPatch?: Partial<ReeSpec>;
  artifactStatusPatch?: Partial<ArtifactStatus>;
  errorMessage?: string;
  successMessage: string;
}

export function planBuildEffect(args: {
  ree: Pick<ReeSpec, "experimentEnvironmentPath">;
}): BuildEffectPlan {
  const experimentEnvironmentTarget =
    args.ree.experimentEnvironmentPath && args.ree.experimentEnvironmentPath !== "__skipped__"
      ? args.ree.experimentEnvironmentPath
      : null;

  return {
    successMessage: `Build complete${experimentEnvironmentTarget ? `; selected experiment environment remains ${experimentEnvironmentTarget}` : ""}`,
  };
}

export function planHbomEffect(): HbomEffectPlan {
  return {
    successMessage: "HBOM profiled from the current machine",
  };
}

export function planSbomEffect(): SbomEffectPlan {
  return {
    reeSpecPatch: { sbom: SBOM_ARTIFACT_PATH },
    successMessage: `SBOM generated — ${SBOM_ARTIFACT_PATH}`,
  };
}

export function planEvaluateEffect(): EvaluateEffectPlan {
  return {
    evaluationStatePatch: {},
    successMessage: "Evaluate complete",
  };
}

export function planActivationEffect(): ActivationEffectPlan {
  return {
    successMessage: "Activation test passed — container started cleanly",
  };
}

export function planStepServiceEffect(args: {
  key: ReeStepKey;
  params: GenericReeStepParams;
  ree: Pick<ReeSpec, "experimentEnvironmentPath">;
  timestamp: string;
  namespaceSuffix: string;
}): StepServiceEffectPlan {
  if (args.key === "build_experiment_environment") {
    return planBuildEffect({ ree: args.ree });
  }

  if (args.key === "hbom") {
    return planHbomEffect();
  }

  if (args.key === "sbom") {
    return planSbomEffect();
  }

  if (args.key === "activation") {
    return planActivationEffect();
  }

  return planEvaluateEffect();
}
