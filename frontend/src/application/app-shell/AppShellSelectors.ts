import { toReeDraftViewModel } from "../../domain/ree/reeDraftViewModel";
import { createAppShellState } from "./AppShellState";
import type { AppShellContextState, AppShellState } from "./AppShellTypes";

export const appShellSelectors = {
  reeDraft: (state: AppShellContextState) => state.reeDraft,
  workspaceRemote: (state: AppShellContextState) => state.workspaceRemote,
  workflowRun: (state: AppShellContextState) => state.workflowRun,
  uiChrome: (state: AppShellContextState) => state.uiChrome,
  reeDraftViewModel: (state: AppShellContextState) =>
    toReeDraftViewModel({
      reeSpec: state.reeDraft.reeSpec,
      workspaceSourceState: state.workspaceRemote.workspaceSourceState,
      artifactStatus: state.workspaceRemote.artifactStatus,
      evaluationState: state.workflowRun.evaluationState,
    }),
  state: (state: AppShellContextState): AppShellState =>
    createAppShellState({
      reeDraft: state.reeDraft,
      workspaceRemote: state.workspaceRemote,
      workflowRun: state.workflowRun,
      uiChrome: state.uiChrome,
    }),
};
