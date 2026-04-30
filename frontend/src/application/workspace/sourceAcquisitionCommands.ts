import type { Ree } from "../../domain/ree/ReeSpec";
import type { LogLine, ReeFile, WorkflowParams } from "../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import { initialAutomationStepParams } from "../workflow/WorkflowStepDefinitions";

export interface SourceOutcomeCommandPayload {
  reePatch: Partial<Ree>;
  sourceSnapshotFiles: FileTreeNode[];
  sourceSnapshotArchiveName: string;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export type SourceCommand =
  | { type: "resetWorkflowOnSourceChange"; workflowParams: WorkflowParams }
  | { type: "setSourceLoading" }
  | {
      type: "hydrateWorkspace";
      workspaceFiles: FileTreeNode[];
      reeArtifactFiles?: ReeFile[];
      ree?: Ree;
    }
  | { type: "applySourcePatchOutcome"; outcome: SourceOutcomeCommandPayload }
  | { type: "setSourceLog"; lines: LogLine[]; ts: string }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export function sourceChangeResetCommands(options: { silent?: boolean } = {}): SourceCommand[] {
  const commands: SourceCommand[] = [
    { type: "resetWorkflowOnSourceChange", workflowParams: initialAutomationStepParams() },
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
        sourceSnapshotFiles: [],
        sourceSnapshotArchiveName: "",
        actionState: "done",
      },
    },
    { type: "toast", message: args.message, toastType: "error" },
  ];
}
