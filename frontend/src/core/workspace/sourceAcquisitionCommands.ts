import type { ArtifactStatus } from "../../core/artifact/ArtifactStatus";
import type { EvaluationState } from "../../core/evaluate/EvaluationState";
import type { ReeSpec } from "../../core/ree/ReeSpec";
import type { LogLine, ReeAssemblyOperationParams, ReeFile } from "../../core/ree/ReeTypes";
import type { FileTreeNode } from "../../core/workspace/FileTree";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";
import { initialReeAssemblyOperationParams } from "../ree-assembly/assemblyCatalog";

export interface SourceOutcomeCommandPayload {
  runId?: string;
  reeSpecPatch?: Partial<ReeSpec>;
  workspaceSourceStatePatch?: Partial<WorkspaceSourceState>;
  sourceSnapshotArchiveName: string;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export type SourceCommand =
  | { type: "resetAssemblyAfterSourceChange"; assemblyOperationParams: ReeAssemblyOperationParams }
  | { type: "setSourceLoading" }
  | { type: "setActiveRunId"; key: string; runId: string }
  | {
      type: "hydrateWorkspace";
      workspaceFiles: FileTreeNode[];
      reeArtifactFiles?: ReeFile[];
      reeSpec?: ReeSpec;
      workspaceSourceState?: WorkspaceSourceState;
      artifactStatus?: ArtifactStatus;
      evaluationState?: EvaluationState;
    }
  | { type: "applySourceOutcome"; outcome: SourceOutcomeCommandPayload }
  | { type: "setSourceLog"; lines: LogLine[]; ts: string }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export function sourceChangeResetCommands(options: { silent?: boolean } = {}): SourceCommand[] {
  const commands: SourceCommand[] = [
    {
      type: "resetAssemblyAfterSourceChange",
      assemblyOperationParams: initialReeAssemblyOperationParams(),
    },
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

export function sourceFailureCommands(args: { message: string; runId?: string }): SourceCommand[] {
  return [
    {
      type: "applySourceOutcome",
      outcome: {
        runId: args.runId,
        reeSpecPatch: {},
        sourceSnapshotArchiveName: "",
        actionState: "done",
      },
    },
    { type: "toast", message: args.message, toastType: "error" },
  ];
}
