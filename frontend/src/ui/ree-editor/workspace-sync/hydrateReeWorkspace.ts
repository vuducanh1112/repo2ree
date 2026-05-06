import type React from "react";
import { patch } from "../../../application/state/actions";
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

    dispatch(
      patch("reeDraft", {
        reeSpec: workspace.ree.reeSpec,
      }),
    );
    dispatch(
      patch("reeDraft", {
        workspaceSourceState: workspace.ree.workspaceSourceState,
      }),
    );
    dispatch(
      patch("reeDraft", {
        artifactStatus: workspace.ree.artifactStatus,
      }),
    );
    dispatch(
      patch("workflowRun", {
        evaluationState: workspace.ree.evaluationState,
      }),
    );
  };
}
