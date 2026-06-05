import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { ReeSpec } from "../ree/ReeSpec";
import type { EvaluationState } from "../review/EvaluationState";
import type { GenericReeAssemblyParams } from "./assemblyStepTypes";
import type { ReeAssemblyOperationKey } from "./assemblyTypes";

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

interface AssemblyServiceEffectPlan {
  persistedFile?: PersistedFilePlan;
  reeSpecPatch?: Partial<ReeSpec>;
  artifactStatusPatch?: Partial<ArtifactStatus>;
  errorMessage?: string;
  successMessage: string;
}

export function planBuildEffect(args: { ree: Pick<ReeSpec, "runtime"> }): BuildEffectPlan {
  const runtimeTarget =
    args.ree.runtime && args.ree.runtime !== "__skipped__" ? args.ree.runtime : null;

  return {
    successMessage: `Build complete${runtimeTarget ? `; selected runtime remains ${runtimeTarget}` : ""}`,
  };
}

export function planHbomEffect(): HbomEffectPlan {
  return {
    successMessage: "HBOM profiled from the current machine",
  };
}

export function planSbomEffect(): SbomEffectPlan {
  return {
    reeSpecPatch: { sbom: "sbom.json" },
    successMessage: "SBOM generated — sbom.json",
  };
}

export function planEvaluateEffect(args: {
  dependencyCount: number;
  manifestCount: number;
}): EvaluateEffectPlan {
  const depSummary = `${args.dependencyCount} dependenc${args.dependencyCount === 1 ? "y" : "ies"} across ${args.manifestCount} manifest file${args.manifestCount === 1 ? "" : "s"}`;

  return {
    evaluationStatePatch: { detectedDependencies: depSummary },
    successMessage: depSummary,
  };
}

export function planActivationEffect(): ActivationEffectPlan {
  return {
    successMessage: "Activation test passed — container started cleanly",
  };
}

export function planAssemblyServiceEffect(args: {
  key: ReeAssemblyOperationKey;
  params: GenericReeAssemblyParams;
  ree: Pick<ReeSpec, "runtime">;
  timestamp: string;
  namespaceSuffix: string;
  dependencyCount: number;
  manifestCount: number;
}): AssemblyServiceEffectPlan {
  if (args.key === "build") {
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

  return planEvaluateEffect({
    dependencyCount: args.dependencyCount,
    manifestCount: args.manifestCount,
  });
}
