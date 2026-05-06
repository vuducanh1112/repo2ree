import type React from "react";
import {
  setArtifactStatus,
  setEvaluationState,
  setWorkspaceSourceState,
  updateReeSpec,
} from "../../../application/state/actions";
import type { AppShellAction } from "../../../application/state/types";
import type { RawReeDraftSlices } from "../../../domain/ree/mapRawReeDraft";
import type { ReeFile } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";

export interface HydratedWorkspaceSnapshot {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  ree?: RawReeDraftSlices;
}

export function createHydrateReeWorkspace(dispatch: React.Dispatch<AppShellAction>) {
  return (workspace: HydratedWorkspaceSnapshot) => {
    if (!workspace.ree) {
      return;
    }
    const ree = workspace.ree;

    dispatch(updateReeSpec(() => ree.reeSpec));
    dispatch(setWorkspaceSourceState(() => ree.workspaceSourceState));
    dispatch(setArtifactStatus(() => ree.artifactStatus));
    dispatch(setEvaluationState(() => ree.evaluationState));
  };
}
