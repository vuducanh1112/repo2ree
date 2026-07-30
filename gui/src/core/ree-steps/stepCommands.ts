import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import type { ReeSpec } from "../ree/ReeSpec";
import type { LogLine, ReeFile, StepRunOutcome } from "../ree/ReeTypes";
import type { FileTreeNode } from "../workspace/FileTree";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import { planStepServiceEffect } from "./stepOutcomePlanning";
import type { ReeStepKey, ReeStepRunParamsByKey } from "./stepRunParams";
import type { GenericReeStepParams } from "./stepTypes";

interface Clock {
  nowIso(): string;
  nowMillis(): number;
}

interface CreateStepCommandPlannersArgs {
  ree: Pick<ReeSpec, "runtime">;
  clock: Clock;
}

export interface StepRunCompletionCommandPayload {
  key: string;
  runId?: string;
  stepRunLog: {
    lines: LogLine[];
    ts: string;
  };
  actionState: "done";
  badge: StepRunOutcome;
  timestamp: string;
}

export type StepCommand =
  | { type: "setActionLoading"; key: string }
  | { type: "setActiveRunId"; key: string; runId: string }
  | { type: "setStepRunLog"; key: string; lines: LogLine[]; ts: string }
  | { type: "completeStepRun"; completion: StepRunCompletionCommandPayload }
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

export type StepCommandPlannerMap = {
  [K in ReeStepKey]: (params: ReeStepRunParamsByKey[K]) => StepCommand[];
};

export function createStepCommandPlanners({
  ree,
  clock,
}: CreateStepCommandPlannersArgs): StepCommandPlannerMap {
  return {
    build: (runParams) =>
      stepEffectPlanToCommands(
        planStepServiceEffect({
          key: "build",
          params: runParams as GenericReeStepParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
        }),
      ),
    hbom: (runParams) =>
      stepEffectPlanToCommands(
        planStepServiceEffect({
          key: "hbom",
          params: runParams as GenericReeStepParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
        }),
      ),
    sbom: (runParams) =>
      stepEffectPlanToCommands(
        planStepServiceEffect({
          key: "sbom",
          params: runParams as GenericReeStepParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
        }),
      ),
    activation: (runParams) =>
      stepEffectPlanToCommands(
        planStepServiceEffect({
          key: "activation",
          params: runParams as GenericReeStepParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
        }),
      ),
    evaluate: (runParams) =>
      stepEffectPlanToCommands(
        planStepServiceEffect({
          key: "evaluate",
          params: runParams as GenericReeStepParams,
          ree,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
        }),
      ),
  };
}

function stepEffectPlanToCommands(plan: {
  persistedFile?: { path: string; content: string };
  reeSpecPatch?: Partial<ReeSpec>;
  artifactStatusPatch?: Partial<ArtifactStatus>;
  evaluationStatePatch?: Partial<EvaluationState>;
  errorMessage?: string;
  successMessage: string;
}): StepCommand[] {
  const commands: StepCommand[] = [];
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

export function nonStepPlanToCommands(plan: {
  reeSpecPatch?: Partial<ReeSpec>;
  lock?: boolean;
  successMessage?: string;
}): StepCommand[] {
  const commands: StepCommand[] = [];
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
