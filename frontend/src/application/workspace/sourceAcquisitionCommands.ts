import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { LogLine, ReeAssemblyOperationParams, ReeFile } from "../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import { initialReeAssemblyOperationParams } from "../ree-assembly/assemblyCatalog";

export interface SourceOutcomeCommandPayload {
  reeSpecPatch?: Partial<ReeSpec>;
  workspaceSourceState?: WorkspaceSourceState;
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

export function sourceFailureCommands(args: { message: string }): SourceCommand[] {
  return [
    {
      type: "applySourceOutcome",
      outcome: {
        reeSpecPatch: {},
        sourceSnapshotArchiveName: "",
        actionState: "done",
      },
    },
    { type: "toast", message: args.message, toastType: "error" },
  ];
}
