import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import type { ActionStates, WorkflowLogs } from "../../domain/ree/ReeTypes";
import type { WorkflowStepCommand } from "../workflow/workflowStepCommands";
import type { SourceCommand } from "./sourceAcquisitionCommands";

type SourceHydrationCommand = Extract<SourceCommand, { type: "hydrateWorkspace" }>;
type SourceResetCommand = Extract<SourceCommand, { type: "resetWorkflowOnSourceChange" }>;
type SourceApplyOutcomeCommand = Extract<SourceCommand, { type: "applySourcePatchOutcome" }>;
type WorkflowRunCompletionCommand = Extract<WorkflowStepCommand, { type: "completeWorkflowRun" }>;
type WorkflowRunHydrationCommand = Extract<WorkflowStepCommand, { type: "hydrateWorkspace" }>;

export type WorkspaceStateCommand =
  | {
      type: "setActionStates";
      actionStates: (prevStates: ActionStates) => ActionStates;
    }
  | {
      type: "setWorkflowLogs";
      workflowLogs: (prevLogs: WorkflowLogs) => WorkflowLogs;
    }
  | {
      type: "completeWorkflowRun";
      completion: WorkflowRunCompletionCommand["completion"];
    }
  | {
      type: "hydrateWorkspace";
      workspace: {
        workspaceFiles:
          | WorkflowRunHydrationCommand["workspaceFiles"]
          | SourceHydrationCommand["workspaceFiles"];
        reeArtifactFiles:
          | NonNullable<WorkflowRunHydrationCommand["reeArtifactFiles"]>
          | NonNullable<SourceHydrationCommand["reeArtifactFiles"]>;
        ree?: WorkflowRunHydrationCommand["ree"] | SourceHydrationCommand["ree"];
      };
    }
  | { type: "setRee"; ree: (prevRee: ReeDraftViewModel) => ReeDraftViewModel }
  | { type: "setLocked"; locked: boolean }
  | {
      type: "resetWorkflowOnSourceChange";
      workflowParams: SourceResetCommand["workflowParams"];
    }
  | {
      type: "applySourcePatchOutcome";
      outcome: SourceApplyOutcomeCommand["outcome"];
    };

export type WorkspaceShellEffect =
  | { type: "dispatchStateCommand"; command: WorkspaceStateCommand }
  | { type: "persistFile"; path: string; content: string }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export function mapWorkflowStepCommandsToEffects(
  commands: WorkflowStepCommand[],
): WorkspaceShellEffect[] {
  return commands.map((command) => {
    if (command.type === "persistFile") {
      return {
        type: "persistFile",
        path: command.path,
        content: command.content,
      };
    }
    if (command.type === "toast") {
      return {
        type: "toast",
        message: command.message,
        toastType: command.toastType,
      };
    }
    if (command.type === "setActionLoading") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "setActionStates",
          actionStates: (prevStates) => ({
            ...prevStates,
            [command.key]: "loading",
          }),
        },
      };
    }
    if (command.type === "setWorkflowRunLog") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "setWorkflowLogs",
          workflowLogs: (prevLogs) => ({
            ...prevLogs,
            [command.key]: { lines: command.lines, ts: command.ts },
          }),
        },
      };
    }
    if (command.type === "completeWorkflowRun") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "completeWorkflowRun",
          completion: command.completion,
        },
      };
    }
    if (command.type === "hydrateWorkspace") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "hydrateWorkspace",
          workspace: {
            workspaceFiles: command.workspaceFiles,
            reeArtifactFiles: command.reeArtifactFiles || [],
            ree: command.ree,
          },
        },
      };
    }
    if (command.type === "patchRee") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "setRee",
          ree: (prevRee) => ({ ...prevRee, ...command.patch }),
        },
      };
    }
    return {
      type: "dispatchStateCommand",
      command: {
        type: "setLocked",
        locked: command.locked,
      },
    };
  });
}

export function mapSourceCommandsToEffects(commands: SourceCommand[]): WorkspaceShellEffect[] {
  return commands.map((command) => {
    if (command.type === "toast") {
      return {
        type: "toast",
        message: command.message,
        toastType: command.toastType,
      };
    }
    if (command.type === "setSourceLoading") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "setActionStates",
          actionStates: (prevStates) => ({
            ...prevStates,
            source: "loading",
          }),
        },
      };
    }
    if (command.type === "setSourceLog") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "setWorkflowLogs",
          workflowLogs: (prevLogs) => ({
            ...prevLogs,
            source: { lines: command.lines, ts: command.ts },
          }),
        },
      };
    }
    if (command.type === "resetWorkflowOnSourceChange") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "resetWorkflowOnSourceChange",
          workflowParams: command.workflowParams,
        },
      };
    }
    if (command.type === "applySourcePatchOutcome") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "applySourcePatchOutcome",
          outcome: command.outcome,
        },
      };
    }
    const hydrationCommand = command as SourceHydrationCommand;
    return {
      type: "dispatchStateCommand",
      command: {
        type: "hydrateWorkspace",
        workspace: {
          workspaceFiles: hydrationCommand.workspaceFiles,
          reeArtifactFiles: hydrationCommand.reeArtifactFiles || [],
          ree: hydrationCommand.ree,
        },
      },
    };
  });
}
