import { createAppShellState } from "./AppShellState";
import type { AppShellContextState, AppShellState } from "./AppShellTypes";

export const appShellSelectors = {
  reeDraft: (state: AppShellContextState) => state.reeDraft,
  workspaceRemote: (state: AppShellContextState) => state.workspaceRemote,
  workflowRun: (state: AppShellContextState) => state.workflowRun,
  uiChrome: (state: AppShellContextState) => state.uiChrome,
  reeDraftViewModel: (state: AppShellContextState): AppShellState["ree"] =>
    createAppShellState({
      reeDraft: state.reeDraft,
      workspaceRemote: state.workspaceRemote,
      workflowRun: state.workflowRun,
      uiChrome: state.uiChrome,
    }).ree,
  state: (state: AppShellContextState): AppShellState =>
    createAppShellState({
      reeDraft: state.reeDraft,
      workspaceRemote: state.workspaceRemote,
      workflowRun: state.workflowRun,
      uiChrome: state.uiChrome,
    }),
};
