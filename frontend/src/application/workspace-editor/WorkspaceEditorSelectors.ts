import { createWorkspaceEditorState } from "./WorkspaceEditorState";
import type { WorkspaceEditorContextState, WorkspaceEditorState } from "./WorkspaceEditorTypes";

export const workspaceEditorSelectors = {
  workspaceDraft: (state: WorkspaceEditorContextState) => state.workspaceDraft,
  workspaceRemote: (state: WorkspaceEditorContextState) => state.workspaceRemote,
  workflowRun: (state: WorkspaceEditorContextState) => state.workflowRun,
  uiChrome: (state: WorkspaceEditorContextState) => state.uiChrome,
  state: (state: WorkspaceEditorContextState): WorkspaceEditorState =>
    createWorkspaceEditorState({
      workspaceDraft: state.workspaceDraft,
      workspaceRemote: state.workspaceRemote,
      workflowRun: state.workflowRun,
      uiChrome: state.uiChrome,
    }),
};
