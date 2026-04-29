import type { WorkspaceEditorContextState, WorkspaceEditorState } from "./workspaceEditorTypes";

export const explorerSelectors = {
  state: (state: WorkspaceEditorContextState): WorkspaceEditorState => state.explorer,
};
