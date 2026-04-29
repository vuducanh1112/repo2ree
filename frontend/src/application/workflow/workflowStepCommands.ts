import type {
  AutomationStepKey,
  AutomationStepRunParamsByKey,
  FileTreeNode,
  LogLine,
  Ree,
  ReeFile,
} from "../../types";
import type { GenericServiceParams } from "../../types/workflowSteps";
import type { WorkspaceEditorClock } from "../workspace/workspaceEditorPorts";
import { scanDependencies } from "./workflowDependencyAnalysis";
import { planWorkflowServiceEffect } from "./workflowOutcomePlanning";

interface CreateWorkflowStepHandlersArgs {
  ree: Ree;
  virtualFiles: FileTreeNode[];
  workspaceServiceMode: "remote" | "mock";
  clock: WorkspaceEditorClock;
}

export interface WorkflowRunCompletionCommandPayload {
  key: string;
  serviceLog: {
    lines: LogLine[];
    ts: string;
  };
  actionState: "done";
  badge: boolean;
  timestamp: string;
}

export type WorkflowStepCommand =
  | { type: "setActionLoading"; key: string }
  | { type: "setWorkflowRunLog"; key: string; lines: LogLine[]; ts: string }
  | { type: "completeWorkflowRun"; completion: WorkflowRunCompletionCommandPayload }
  | {
      type: "hydrateWorkspace";
      virtualFiles: FileTreeNode[];
      workspaceReeFiles?: ReeFile[];
      ree?: Ree;
    }
  | { type: "persistFile"; path: string; content: string }
  | { type: "patchRee"; patch: Partial<Ree> }
  | { type: "setLocked"; locked: boolean }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export type WorkflowStepHandlerMap = {
  [K in AutomationStepKey]: (
    params: AutomationStepRunParamsByKey[K],
    newLevel: number,
  ) => WorkflowStepCommand[];
};

export function createWorkflowStepHandlers({
  ree,
  virtualFiles,
  workspaceServiceMode,
  clock,
}: CreateWorkflowStepHandlersArgs): WorkflowStepHandlerMap {
  return {
    build: (runParams, newLevel) =>
      workflowEffectPlanToCommands(
        planWorkflowServiceEffect({
          key: "build",
          params: runParams as GenericServiceParams,
          ree,
          newLevel,
          workspaceServiceMode,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount: 0,
          manifestCount: 0,
        }),
      ),
    hbom: (runParams, newLevel) =>
      workflowEffectPlanToCommands(
        planWorkflowServiceEffect({
          key: "hbom",
          params: runParams as GenericServiceParams,
          ree,
          newLevel,
          workspaceServiceMode,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount: 0,
          manifestCount: 0,
        }),
      ),
    sbom: (runParams, newLevel) =>
      workflowEffectPlanToCommands(
        planWorkflowServiceEffect({
          key: "sbom",
          params: runParams as GenericServiceParams,
          ree,
          newLevel,
          workspaceServiceMode,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount: 0,
          manifestCount: 0,
        }),
      ),
    activation: (runParams, newLevel) =>
      workflowEffectPlanToCommands(
        planWorkflowServiceEffect({
          key: "activation",
          params: runParams as GenericServiceParams,
          ree,
          newLevel,
          workspaceServiceMode,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount: 0,
          manifestCount: 0,
        }),
      ),
    evaluate: (runParams, newLevel) => {
      const groups = scanDependencies(virtualFiles || []);
      const dependencyCount = groups.reduce((sum, group) => sum + group.packages.length, 0);
      return workflowEffectPlanToCommands(
        planWorkflowServiceEffect({
          key: "evaluate",
          params: runParams as GenericServiceParams,
          ree,
          newLevel,
          workspaceServiceMode,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount,
          manifestCount: groups.length,
        }),
      );
    },
  };
}

function workflowEffectPlanToCommands(plan: {
  persistedFile?: { path: string; content: string };
  reePatch?: Partial<Ree>;
  errorMessage?: string;
  successMessage: string;
}): WorkflowStepCommand[] {
  const commands: WorkflowStepCommand[] = [];
  if (plan.persistedFile) {
    commands.push({
      type: "persistFile",
      path: plan.persistedFile.path,
      content: plan.persistedFile.content,
    });
  }
  if (plan.reePatch) {
    commands.push({ type: "patchRee", patch: plan.reePatch });
  }
  if (plan.errorMessage) {
    commands.push({ type: "toast", message: plan.errorMessage, toastType: "error" });
  }
  commands.push({ type: "toast", message: plan.successMessage, toastType: "success" });
  return commands;
}

export function nonWorkflowPlanToCommands(plan: {
  reePatch?: Partial<Ree>;
  lock?: boolean;
  successMessage?: string;
}): WorkflowStepCommand[] {
  const commands: WorkflowStepCommand[] = [];
  if (plan.reePatch) {
    commands.push({ type: "patchRee", patch: plan.reePatch });
  }
  if (plan.lock) {
    commands.push({ type: "setLocked", locked: true });
  }
  if (plan.successMessage) {
    commands.push({ type: "toast", message: plan.successMessage, toastType: "success" });
  }
  return commands;
}
