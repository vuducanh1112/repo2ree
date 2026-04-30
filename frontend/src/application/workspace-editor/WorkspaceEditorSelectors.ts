import type { WorkspaceEditorContextState, WorkspaceEditorState } from "./WorkspaceEditorTypes";

export const workspaceEditorSelectors = {
  state: (state: WorkspaceEditorContextState): WorkspaceEditorState => state.workspaceEditor,
};
