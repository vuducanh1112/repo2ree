import { initialAutomationStepParams } from "../../constants/workflowSteps";
import type { FileTreeNode, LogLine, Ree, ReeFile, ServiceParams } from "../../types";

export interface SourceOutcomeCommandPayload {
  reePatch: Partial<Ree>;
  immutableSourceSnapshotFiles: FileTreeNode[];
  immutableSourceSnapshotArchiveName: string;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export type SourceCommand =
  | { type: "resetWorkflowOnSourceChange"; serviceParams: ServiceParams }
  | { type: "setSourceLoading" }
  | {
      type: "hydrateWorkspace";
      virtualFiles: FileTreeNode[];
      workspaceReeFiles?: ReeFile[];
      ree?: Ree;
    }
  | { type: "applySourcePatchOutcome"; outcome: SourceOutcomeCommandPayload }
  | { type: "setSourceLog"; lines: LogLine[]; ts: string }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export function sourceChangeResetCommands(options: { silent?: boolean } = {}): SourceCommand[] {
  const commands: SourceCommand[] = [
    { type: "resetWorkflowOnSourceChange", serviceParams: initialAutomationStepParams() },
  ];
  if (!options.silent) {
    commands.push({
      type: "toast",
      message: "Source changed — downstream status and scripts reset",
      toastType: "info",
    });
  }
  return commands;
}

export function sourceFailureCommands(args: { message: string }): SourceCommand[] {
  return [
    {
      type: "applySourcePatchOutcome",
      outcome: {
        reePatch: {},
        immutableSourceSnapshotFiles: [],
        immutableSourceSnapshotArchiveName: "",
        actionState: "done",
      },
    },
    { type: "toast", message: args.message, toastType: "error" },
  ];
}
