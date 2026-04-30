import type { Ree } from "../../domain/ree/ReeSpec";
import type { ActionStates, ServiceLogs } from "../../domain/ree/ReeTypes";
import type { WorkflowStepCommand } from "../workflow/workflowStepCommands";
import type { SourceCommand } from "./sourceAcquisitionCommands";

type SourceHydrationCommand = Extract<SourceCommand, { type: "hydrateWorkspace" }>;
type SourceResetCommand = Extract<SourceCommand, { type: "resetWorkflowOnSourceChange" }>;
type SourceApplyOutcomeCommand = Extract<SourceCommand, { type: "applySourcePatchOutcome" }>;
type WorkflowRunCompletionCommand = Extract<WorkflowStepCommand, { type: "completeWorkflowRun" }>;
type WorkflowRunHydrationCommand = Extract<WorkflowStepCommand, { type: "hydrateWorkspace" }>;

export type ExplorerStateCommand =
  | {
      type: "setActionStates";
      actionStates: (prevStates: ActionStates) => ActionStates;
    }
  | {
      type: "setServiceLogs";
      serviceLogs: (prevLogs: ServiceLogs) => ServiceLogs;
    }
  | {
      type: "completeServiceRun";
      completion: WorkflowRunCompletionCommand["completion"];
    }
  | {
      type: "hydrateWorkspace";
      workspace: {
        virtualFiles:
          | WorkflowRunHydrationCommand["virtualFiles"]
          | SourceHydrationCommand["virtualFiles"];
        workspaceReeFiles:
          | NonNullable<WorkflowRunHydrationCommand["workspaceReeFiles"]>
          | NonNullable<SourceHydrationCommand["workspaceReeFiles"]>;
        ree?: WorkflowRunHydrationCommand["ree"] | SourceHydrationCommand["ree"];
      };
    }
  | { type: "setRee"; ree: (prevRee: Ree) => Ree }
  | { type: "setLocked"; locked: boolean }
  | {
      type: "resetWorkflowOnSourceChange";
      serviceParams: SourceResetCommand["serviceParams"];
    }
  | {
      type: "applySourcePatchOutcome";
      outcome: SourceApplyOutcomeCommand["outcome"];
    };

export type ExplorerShellEffect =
  | { type: "dispatchStateCommand"; command: ExplorerStateCommand }
  | { type: "persistFile"; path: string; content: string }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export function mapWorkflowStepCommandsToEffects(
  commands: WorkflowStepCommand[],
): ExplorerShellEffect[] {
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
          type: "setServiceLogs",
          serviceLogs: (prevLogs) => ({
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
          type: "completeServiceRun",
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
            virtualFiles: command.virtualFiles,
            workspaceReeFiles: command.workspaceReeFiles || [],
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

export function mapSourceCommandsToEffects(commands: SourceCommand[]): ExplorerShellEffect[] {
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
          type: "setServiceLogs",
          serviceLogs: (prevLogs) => ({
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
          serviceParams: command.serviceParams,
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
          virtualFiles: hydrationCommand.virtualFiles,
          workspaceReeFiles: hydrationCommand.workspaceReeFiles || [],
          ree: hydrationCommand.ree,
        },
      },
    };
  });
}
