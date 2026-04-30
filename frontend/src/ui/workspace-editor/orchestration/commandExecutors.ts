import type { WorkflowStepCommand } from "../../../application/workflow/workflowStepCommands";
import type { SourceCommand } from "../../../application/workspace/sourceAcquisitionCommands";
import {
  mapSourceCommandsToEffects,
  mapWorkflowStepCommandsToEffects,
  type WorkspaceShellEffect,
  type WorkspaceStateCommand,
} from "../../../application/workspace/workspaceMutationEffects";
import type { WorkspaceEditorAction } from "../../../application/workspace-editor";
import { workspaceEditorActions } from "../../../application/workspace-editor";
import type { ShowToast } from "./types";

export type WorkspaceWorkflowDispatch = (action: WorkspaceEditorAction) => void;

interface WorkflowStepCommandEffects {
  dispatch: WorkspaceWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
}

function dispatchWorkspaceStateCommand(
  command: WorkspaceStateCommand,
  dispatch: WorkspaceWorkflowDispatch,
): void {
  if (command.type === "setActionStates") {
    dispatch(workspaceEditorActions.setActionStates(command.actionStates));
  } else if (command.type === "setServiceLogs") {
    dispatch(workspaceEditorActions.setServiceLogs(command.serviceLogs));
  } else if (command.type === "completeServiceRun") {
    dispatch(workspaceEditorActions.completeWorkflowRun(command.completion));
  } else if (command.type === "hydrateWorkspace") {
    dispatch(workspaceEditorActions.hydrateWorkspace(command.workspace));
  } else if (command.type === "setRee") {
    dispatch(workspaceEditorActions.setRee(command.ree));
  } else if (command.type === "setLocked") {
    dispatch(workspaceEditorActions.setLocked(command.locked));
  } else if (command.type === "resetWorkflowOnSourceChange") {
    dispatch(workspaceEditorActions.resetWorkflowOnSourceChange(command.serviceParams));
  } else {
    dispatch(workspaceEditorActions.applySourcePatchOutcome(command.outcome));
  }
}

function executeWorkspaceEffects(
  effects: WorkspaceShellEffect[],
  handlers: WorkflowStepCommandEffects,
): void {
  for (const effect of effects) {
    if (effect.type === "dispatchStateCommand") {
      dispatchWorkspaceStateCommand(effect.command, handlers.dispatch);
    } else if (effect.type === "persistFile") {
      handlers.persistWorkspaceFile(effect.path, effect.content);
    } else {
      handlers.showToast(effect.message, effect.toastType);
    }
  }
}

export function executeWorkflowStepCommands(
  commands: WorkflowStepCommand[],
  effects: WorkflowStepCommandEffects,
): void {
  executeWorkspaceEffects(mapWorkflowStepCommandsToEffects(commands), effects);
}

interface SourceCommandEffects {
  dispatch: WorkspaceWorkflowDispatch;
  showToast: ShowToast;
}

export function executeSourceCommands(
  commands: SourceCommand[],
  effects: SourceCommandEffects,
): void {
  executeWorkspaceEffects(mapSourceCommandsToEffects(commands), {
    ...effects,
    persistWorkspaceFile: () => {},
  });
}
