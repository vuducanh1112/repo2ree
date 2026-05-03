import { createAppShellState } from "./AppShellState";
import type { AppShellContextState, AppShellState } from "./AppShellTypes";

export const appShellSelectors = {
  reeDraft: (state: AppShellContextState) => state.reeDraft,
  workflowRun: (state: AppShellContextState) => state.workflowRun,
  uiChrome: (state: AppShellContextState) => state.uiChrome,
  state: (state: AppShellContextState): AppShellState =>
    createAppShellState({
      reeDraft: state.reeDraft,
      workflowRun: state.workflowRun,
      uiChrome: state.uiChrome,
    }),
};
