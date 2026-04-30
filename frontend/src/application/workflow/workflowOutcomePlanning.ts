import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import { LEVELS } from "../../domain/review/levels";
import type { GenericWorkflowParams } from "./WorkflowStepTypes";
import type { AutomationStepKey } from "./WorkflowTypes";

interface PersistedFilePlan {
  path: string;
  content: string;
}

interface BuildEffectPlan {
  persistedFile?: PersistedFilePlan;
  reePatch?: Partial<ReeDraftViewModel>;
  errorMessage?: string;
  successMessage: string;
}

interface SbomEffectPlan {
  persistedFile?: PersistedFilePlan;
  reePatch: Partial<ReeDraftViewModel>;
  successMessage: string;
}

interface HbomEffectPlan {
  reePatch?: Partial<ReeDraftViewModel>;
  successMessage: string;
}

interface EvaluateEffectPlan {
  reePatch: Partial<ReeDraftViewModel>;
  successMessage: string;
}

interface ActivationEffectPlan {
  successMessage: string;
}

interface WorkflowServiceEffectPlan {
  persistedFile?: PersistedFilePlan;
  reePatch?: Partial<ReeDraftViewModel>;
  errorMessage?: string;
  successMessage: string;
}

export function planBuildEffect(args: {
  ree: ReeDraftViewModel;
  expectedOutput?: string;
}): BuildEffectPlan {
  const runtimeTarget =
    args.ree.runtime && args.ree.runtime !== "__skipped__" ? args.ree.runtime : null;
  const expectedOutput = String(args.expectedOutput || "").trim();
  const producedName = expectedOutput || runtimeTarget || "runtime.tar.gz";

  if (expectedOutput) {
    return {
      reePatch: {
        runtime: expectedOutput,
        runtimeIncluded: true,
      },
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
    reePatch: { sbom: "sbom.json" },
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
    reePatch: {
      evalLevel: args.newLevel,
      repro_level: `L${args.newLevel} · ${label}`,
      detected_dependencies: depSummary,
    },
    successMessage: `L${args.newLevel} · ${label}`,
  };
}

export function planActivationEffect(): ActivationEffectPlan {
  return {
    successMessage: "Activation test passed — container started cleanly",
  };
}

export function planWorkflowServiceEffect(args: {
  key: AutomationStepKey;
  params: GenericWorkflowParams;
  ree: ReeDraftViewModel;
  newLevel: number;
  timestamp: string;
  namespaceSuffix: string;
  dependencyCount: number;
  manifestCount: number;
}): WorkflowServiceEffectPlan {
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
