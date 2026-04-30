import { createWorkspaceShellState } from "./WorkspaceShellState";
import type { WorkspaceShellContextState, WorkspaceShellState } from "./WorkspaceShellTypes";

export const workspaceShellSelectors = {
  workspaceDraft: (state: WorkspaceShellContextState) => state.workspaceDraft,
  workspaceRemote: (state: WorkspaceShellContextState) => state.workspaceRemote,
  workflowRun: (state: WorkspaceShellContextState) => state.workflowRun,
  uiChrome: (state: WorkspaceShellContextState) => state.uiChrome,
  state: (state: WorkspaceShellContextState): WorkspaceShellState =>
    createWorkspaceShellState({
      workspaceDraft: state.workspaceDraft,
      workspaceRemote: state.workspaceRemote,
      workflowRun: state.workflowRun,
      uiChrome: state.uiChrome,
    }),
};
