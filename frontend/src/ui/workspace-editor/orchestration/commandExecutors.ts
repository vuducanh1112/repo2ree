import type { WorkflowStepCommand } from "../../../application/workflow/workflowStepCommands";
import type { SourceCommand } from "../../../application/workspace/sourceAcquisitionCommands";
import {
  type ExplorerShellEffect,
  type ExplorerStateCommand,
  mapSourceCommandsToEffects,
  mapWorkflowStepCommandsToEffects,
} from "../../../application/workspace/workspaceMutationEffects";
import type { WorkspaceEditorAction } from "../../../application/workspace-editor";
import { workspaceEditorActions } from "../../../application/workspace-editor";
import type { ShowToast } from "./types";

export type ExplorerWorkflowDispatch = (action: WorkspaceEditorAction) => void;

interface WorkflowStepCommandEffects {
  dispatch: ExplorerWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
}

function dispatchExplorerStateCommand(
  command: ExplorerStateCommand,
  dispatch: ExplorerWorkflowDispatch,
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

function executeExplorerEffects(
  effects: ExplorerShellEffect[],
  handlers: WorkflowStepCommandEffects,
): void {
  for (const effect of effects) {
    if (effect.type === "dispatchStateCommand") {
      dispatchExplorerStateCommand(effect.command, handlers.dispatch);
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
  executeExplorerEffects(mapWorkflowStepCommandsToEffects(commands), effects);
}

interface SourceCommandEffects {
  dispatch: ExplorerWorkflowDispatch;
  showToast: ShowToast;
}

export function executeSourceCommands(
  commands: SourceCommand[],
  effects: SourceCommandEffects,
): void {
  executeExplorerEffects(mapSourceCommandsToEffects(commands), {
    ...effects,
    persistWorkspaceFile: () => {},
  });
}
