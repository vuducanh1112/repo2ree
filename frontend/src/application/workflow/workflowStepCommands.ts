import type { Ree } from "../../domain/ree/ReeSpec";
import type { LogLine, ReeFile } from "../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { WorkspaceEditorClock } from "../workspace-editor/WorkspaceEditorPorts";
import type { GenericWorkflowParams } from "./WorkflowStepTypes";
import type { AutomationStepKey, AutomationStepRunParamsByKey } from "./WorkflowTypes";
import { scanDependencies } from "./workflowDependencyAnalysis";
import { planWorkflowServiceEffect } from "./workflowOutcomePlanning";

interface CreateWorkflowStepHandlersArgs {
  ree: Ree;
  workspaceFiles: FileTreeNode[];
  clock: WorkspaceEditorClock;
}

export interface WorkflowRunCompletionCommandPayload {
  key: string;
  workflowLog: {
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
      workspaceFiles: FileTreeNode[];
      reeArtifactFiles?: ReeFile[];
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
  workspaceFiles,
  clock,
}: CreateWorkflowStepHandlersArgs): WorkflowStepHandlerMap {
  return {
    build: (runParams, newLevel) =>
      workflowEffectPlanToCommands(
        planWorkflowServiceEffect({
          key: "build",
          params: runParams as GenericWorkflowParams,
          ree,
          newLevel,
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
          params: runParams as GenericWorkflowParams,
          ree,
          newLevel,
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
          params: runParams as GenericWorkflowParams,
          ree,
          newLevel,
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
          params: runParams as GenericWorkflowParams,
          ree,
          newLevel,
          timestamp: clock.nowIso(),
          namespaceSuffix: String(clock.nowMillis()),
          dependencyCount: 0,
          manifestCount: 0,
        }),
      ),
    evaluate: (runParams, newLevel) => {
      const groups = scanDependencies(workspaceFiles || []);
      const dependencyCount = groups.reduce((sum, group) => sum + group.packages.length, 0);
      return workflowEffectPlanToCommands(
        planWorkflowServiceEffect({
          key: "evaluate",
          params: runParams as GenericWorkflowParams,
          ree,
          newLevel,
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
