import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import type { ReeSpec } from "../ree/ReeSpec";
import type { AssemblyRunOutcome, LogLine, ReeFile } from "../ree/ReeTypes";
import type { FileTreeNode } from "../workspace/FileTree";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import { scanDependencies } from "./assemblyDependencyAnalysis";
import { planAssemblyServiceEffect } from "./assemblyOutcomePlanning";
import type { GenericReeAssemblyParams } from "./assemblyStepTypes";
import type { ReeAssemblyOperationKey, ReeAssemblyRunParamsByKey } from "./assemblyTypes";

interface Clock {
  nowIso(): string;
  nowMillis(): number;
}

interface CreateAssemblyCommandPlannersArgs {
  ree: Pick<ReeSpec, "runtime">;
  workspaceFiles: FileTreeNode[];
  clock: Clock;
}

export interface AssemblyRunCompletionCommandPayload {
  key: string;
  runId?: string;
  assemblyRunLog: {
    lines: LogLine[];
    ts: string;
  };
  actionState: "done";
  badge: AssemblyRunOutcome;
  timestamp: string;
}

export type AssemblyCommand =
  | { type: "setActionLoading"; key: string }
  | { type: "setActiveRunId"; key: string; runId: string }
  | { type: "setAssemblyRunLog"; key: string; lines: LogLine[]; ts: string }
  | { type: "completeAssemblyRun"; completion: AssemblyRunCompletionCommandPayload }
  | {
      type: "hydrateWorkspace";
      workspaceFiles: FileTreeNode[];
      reeArtifactFiles?: ReeFile[];
      reeSpec?: ReeSpec;
      workspaceSourceState?: WorkspaceSourceState;
      artifactStatus?: ArtifactStatus;
      evaluationState?: EvaluationState;
    }
  | { type: "persistFile"; path: string; content: string }
  | { type: "setReeSpec"; reeSpec: Partial<ReeSpec> }
  | { type: "setArtifactStatus"; artifactStatus: Partial<ArtifactStatus> }
  | { type: "setEvaluationState"; evaluationState: Partial<EvaluationState> }
  | { type: "setLocked"; locked: boolean }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export type AssemblyCommandPlannerMap = {
  [K in ReeAssemblyOperationKey]: (params: ReeAssemblyRunParamsByKey[K]) => AssemblyCommand[];
};

export function createAssemblyCommandPlanners({
  ree,
  workspaceFiles,
  clock,
}: CreateAssemblyCommandPlannersArgs): AssemblyCommandPlannerMap {
  return {
    build: (runParams) =>
      assemblyEffectPlanToCommands(
        planAssemblyServiceEffect({
          key: "build",
          params: runParams as GenericReeAssemblyParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount: 0,
          manifestCount: 0,
        }),
      ),
    hbom: (runParams) =>
      assemblyEffectPlanToCommands(
        planAssemblyServiceEffect({
          key: "hbom",
          params: runParams as GenericReeAssemblyParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount: 0,
          manifestCount: 0,
        }),
      ),
    sbom: (runParams) =>
      assemblyEffectPlanToCommands(
        planAssemblyServiceEffect({
          key: "sbom",
          params: runParams as GenericReeAssemblyParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount: 0,
          manifestCount: 0,
        }),
      ),
    activation: (runParams) =>
      assemblyEffectPlanToCommands(
        planAssemblyServiceEffect({
          key: "activation",
          params: runParams as GenericReeAssemblyParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount: 0,
          manifestCount: 0,
        }),
      ),
    evaluate: (runParams) => {
      const groups = scanDependencies(workspaceFiles || []);
      const dependencyCount = groups.reduce((sum, group) => sum + group.packages.length, 0);
      return assemblyEffectPlanToCommands(
        planAssemblyServiceEffect({
          key: "evaluate",
          params: runParams as GenericReeAssemblyParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount,
          manifestCount: groups.length,
        }),
      );
    },
  };
}

function assemblyEffectPlanToCommands(plan: {
  persistedFile?: { path: string; content: string };
  reeSpecPatch?: Partial<ReeSpec>;
  artifactStatusPatch?: Partial<ArtifactStatus>;
  evaluationStatePatch?: Partial<EvaluationState>;
  errorMessage?: string;
  successMessage: string;
}): AssemblyCommand[] {
  const commands: AssemblyCommand[] = [];
  if (plan.persistedFile) {
    commands.push({
      type: "persistFile",
      path: plan.persistedFile.path,
      content: plan.persistedFile.content,
    });
  }
  if (plan.reeSpecPatch) {
    commands.push({ type: "setReeSpec", reeSpec: plan.reeSpecPatch });
  }
  if (plan.artifactStatusPatch) {
    commands.push({ type: "setArtifactStatus", artifactStatus: plan.artifactStatusPatch });
  }
  if (plan.evaluationStatePatch) {
    commands.push({ type: "setEvaluationState", evaluationState: plan.evaluationStatePatch });
  }
  if (plan.errorMessage) {
    commands.push({ type: "toast", message: plan.errorMessage, toastType: "error" });
  }
  commands.push({ type: "toast", message: plan.successMessage, toastType: "success" });
  return commands;
}

export function nonAssemblyPlanToCommands(plan: {
  reeSpecPatch?: Partial<ReeSpec>;
  lock?: boolean;
  successMessage?: string;
}): AssemblyCommand[] {
  const commands: AssemblyCommand[] = [];
  if (plan.reeSpecPatch) {
    commands.push({ type: "setReeSpec", reeSpec: plan.reeSpecPatch });
  }
  if (plan.lock) {
    commands.push({ type: "setLocked", locked: true });
  }
  if (plan.successMessage) {
    commands.push({ type: "toast", message: plan.successMessage, toastType: "success" });
  }
  return commands;
}
