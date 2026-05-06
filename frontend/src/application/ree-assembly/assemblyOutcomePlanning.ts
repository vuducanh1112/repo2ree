import type { ArtifactStatus } from "../../core/artifact/ArtifactStatus";
import type { ReeSpec } from "../../core/ree/ReeSpec";
import type { EvaluationState } from "../../core/review/EvaluationState";
import { LEVELS } from "../../core/review/levels";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
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
  reeSpecPatch: Partial<ReeSpec>;
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
  evaluationStatePatch?: Partial<EvaluationState>;
  errorMessage?: string;
  successMessage: string;
}

export function planBuildEffect(args: {
  ree: ReeEditorViewModel;
  expectedOutput?: string;
}): BuildEffectPlan {
  const runtimeTarget =
    args.ree.runtime && args.ree.runtime !== "__skipped__" ? args.ree.runtime : null;
  const expectedOutput = String(args.expectedOutput || "").trim();
  const producedName = expectedOutput || runtimeTarget || "runtime.tar.gz";

  if (expectedOutput) {
    return {
      reeSpecPatch: { runtime: expectedOutput },
      artifactStatusPatch: { runtimeIncluded: true },
      successMessage: `Build complete${producedName ? ` — ${producedName} produced` : ""}`,
    };
  }

  return {
    successMessage: `Build complete${producedName ? ` — ${producedName} produced` : ""}`,
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
  newLevel: number;
  dependencyCount: number;
  manifestCount: number;
}): EvaluateEffectPlan {
  const label = LEVELS[Math.min(args.newLevel, 7)].label;
  const depSummary = `${args.dependencyCount} dependenc${args.dependencyCount === 1 ? "y" : "ies"} across ${args.manifestCount} manifest file${args.manifestCount === 1 ? "" : "s"}`;

  return {
    reeSpecPatch: {
      repro_level: `L${args.newLevel} · ${label}`,
      detected_dependencies: depSummary,
    },
    evaluationStatePatch: { evalLevel: args.newLevel },
    successMessage: `L${args.newLevel} · ${label}`,
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
  ree: ReeEditorViewModel;
  newLevel: number;
  timestamp: string;
  namespaceSuffix: string;
  dependencyCount: number;
  manifestCount: number;
}): AssemblyServiceEffectPlan {
  if (args.key === "build") {
    return planBuildEffect({
      ree: args.ree,
      expectedOutput: args.params._expectedOutput ? String(args.params._expectedOutput) : "",
    });
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
    newLevel: args.newLevel,
    dependencyCount: args.dependencyCount,
    manifestCount: args.manifestCount,
  });
}
