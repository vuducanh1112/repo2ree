import type {
  AutomationStepKey,
  AutomationStepRunParamsByKey,
  FileTreeNode,
  LogLine,
  Ree,
  ReeFile,
} from "../../types";
import type { GenericServiceParams } from "../../types/services";
import { scanDependencies } from "./dependencyParser";
import type { ExplorerClock } from "./runtimePorts";
import { planWorkflowServiceEffect } from "./serviceEffectsPlanning";

interface CreateServiceRunHandlersArgs {
  ree: Ree;
  virtualFiles: FileTreeNode[];
  workspaceServiceMode: "remote" | "mock";
  clock: ExplorerClock;
}

export interface ServiceRunCompletionCommandPayload {
  key: string;
  serviceLog: {
    lines: LogLine[];
    ts: string;
  };
  actionState: "done";
  badge: boolean;
  timestamp: string;
}

export type ServiceRunCommand =
  | { type: "setActionLoading"; key: string }
  | { type: "setServiceLog"; key: string; lines: LogLine[]; ts: string }
  | { type: "completeServiceRun"; completion: ServiceRunCompletionCommandPayload }
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

export type ServiceRunHandlerMap = {
  [K in AutomationStepKey]: (
    params: AutomationStepRunParamsByKey[K],
    newLevel: number,
  ) => ServiceRunCommand[];
};

export function createServiceRunHandlers({
  ree,
  virtualFiles,
  workspaceServiceMode,
  clock,
}: CreateServiceRunHandlersArgs): ServiceRunHandlerMap {
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
}): ServiceRunCommand[] {
  const commands: ServiceRunCommand[] = [];
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
}): ServiceRunCommand[] {
  const commands: ServiceRunCommand[] = [];
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
