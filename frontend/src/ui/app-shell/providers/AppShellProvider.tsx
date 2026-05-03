import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import { normalizeUiChromePage } from "../../../application/app-shell/AppShellState";
import type {
  AppShellAction,
  AppShellContextState,
} from "../../../application/app-shell/AppShellTypes";
import {
  createInitialReeDraftState,
  resolveReeDraftUpdater,
} from "../../../application/ree-draft/ReeDraftState";
import {
  createInitialUiChromeState,
  resolveUiChromeUpdater,
} from "../../../application/ui-chrome/UiChromeState";
import {
  createInitialWorkflowRunState,
  resolveWorkflowRunUpdater,
} from "../../../application/workflow-runs/WorkflowRunState";
import { enforceSourceOriginRules } from "../../../domain/artifact/sourceOriginRules";
import {
  createEmptyReeViewState,
  type ReeViewState,
  splitReeViewState,
  toReeViewState,
} from "../../../domain/ree/ReeViewState";
import { computeSourceChangeConsequences } from "../../../domain/workspace/sourceChangeConsequences";

interface AppShellContextValue {
  state: AppShellContextState;
  dispatch: React.Dispatch<AppShellAction>;
}

const AppShellContext = createContext<AppShellContextValue | null>(null);

interface AppShellProviderProps {
  children: ReactNode;
  initialRee?: ReeViewState;
}

export function createInitialState(
  initialRee: ReeViewState = createEmptyReeViewState(),
): AppShellContextState {
  const normalizedRee = enforceSourceOriginRules(initialRee);
  const split = splitReeViewState(normalizedRee);
  return {
    reeDraft: {
      ...createInitialReeDraftState(normalizedRee),
      workspaceSourceState: split.workspaceSourceState,
      artifactStatus: split.artifactStatus,
    },
    workflowRun: {
      ...createInitialWorkflowRunState(),
      evaluationState: split.evaluationState,
    },
    uiChrome: createInitialUiChromeState(),
  };
}

function buildReeViewFromState(state: AppShellContextState): ReeViewState {
  return toReeViewState({
    reeSpec: state.reeDraft.reeSpec,
    workspaceSourceState: state.reeDraft.workspaceSourceState,
    artifactStatus: state.reeDraft.artifactStatus,
    evaluationState: state.workflowRun.evaluationState,
  });
}

export function appShellReducer(
  state: AppShellContextState,
  action: AppShellAction,
): AppShellContextState {
  switch (action.type) {
    case "appShell/setReeSpec":
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          reeSpec: resolveReeDraftUpdater(state.reeDraft.reeSpec, action.reeSpec),
        },
      };
    case "appShell/setLocked":
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          locked: resolveReeDraftUpdater(state.reeDraft.locked, action.locked),
        },
      };
    case "appShell/setRepoMode":
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          repoMode: resolveReeDraftUpdater(state.reeDraft.repoMode, action.repoMode),
        },
      };
    case "appShell/setWorkspaceSourceState":
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          workspaceSourceState: resolveReeDraftUpdater(
            state.reeDraft.workspaceSourceState,
            action.workspaceSourceState,
          ),
        },
      };
    case "appShell/setArtifactStatus":
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          artifactStatus: resolveReeDraftUpdater(
            state.reeDraft.artifactStatus,
            action.artifactStatus,
          ),
        },
      };
    case "appShell/setActionStates":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          actionStates: resolveWorkflowRunUpdater(
            state.workflowRun.actionStates,
            action.actionStates,
          ),
        },
      };
    case "appShell/setBadges":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          badges: resolveWorkflowRunUpdater(state.workflowRun.badges, action.badges),
        },
      };
    case "appShell/setTimestamps":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          timestamps: resolveWorkflowRunUpdater(state.workflowRun.timestamps, action.timestamps),
        },
      };
    case "appShell/setWorkflowParams":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          workflowParams: resolveWorkflowRunUpdater(
            state.workflowRun.workflowParams,
            action.workflowParams,
          ),
        },
      };
    case "appShell/setEvaluationState":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          evaluationState: resolveWorkflowRunUpdater(
            state.workflowRun.evaluationState,
            action.evaluationState,
          ),
        },
      };
    case "appShell/setActiveRunId":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          activeRunIds: {
            ...state.workflowRun.activeRunIds,
            [action.payload.key]: action.payload.runId,
          },
        },
      };
    case "appShell/setToast":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          toast: resolveUiChromeUpdater(state.uiChrome.toast, action.toast),
        },
      };
    case "appShell/setPage": {
      const candidate = resolveUiChromeUpdater(state.uiChrome.page, action.page);
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          page: normalizeUiChromePage(candidate, state.uiChrome.page),
        },
      };
    }
    case "appShell/setFocusedField":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          focusedField: resolveUiChromeUpdater(state.uiChrome.focusedField, action.focusedField),
        },
      };
    case "appShell/setNavCollapsed":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          navCollapsed: resolveUiChromeUpdater(state.uiChrome.navCollapsed, action.navCollapsed),
        },
      };
    case "appShell/setSourceSnapshotArchiveName":
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          sourceSnapshotArchiveName: resolveReeDraftUpdater(
            state.reeDraft.sourceSnapshotArchiveName,
            action.sourceSnapshotArchiveName,
          ),
        },
      };
    case "appShell/applySourceOutcome":
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          reeSpec: action.outcome.reeSpecPatch
            ? {
                ...state.reeDraft.reeSpec,
                ...action.outcome.reeSpecPatch,
              }
            : state.reeDraft.reeSpec,
          workspaceSourceState: action.outcome.workspaceSourceState
            ? {
                ...state.reeDraft.workspaceSourceState,
                ...action.outcome.workspaceSourceState,
              }
            : state.reeDraft.workspaceSourceState,
          sourceSnapshotArchiveName: action.outcome.sourceSnapshotArchiveName,
        },
        workflowRun: {
          ...state.workflowRun,
          actionStates: action.outcome.actionState
            ? { ...state.workflowRun.actionStates, source: action.outcome.actionState }
            : state.workflowRun.actionStates,
          badges:
            typeof action.outcome.badge === "boolean"
              ? { ...state.workflowRun.badges, source: action.outcome.badge }
              : state.workflowRun.badges,
          timestamps: action.outcome.timestamp
            ? { ...state.workflowRun.timestamps, source: action.outcome.timestamp }
            : state.workflowRun.timestamps,
        },
      };
    case "appShell/setShowReviewPreview":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          showReviewPreview: resolveUiChromeUpdater(
            state.uiChrome.showReviewPreview,
            action.showReviewPreview,
          ),
        },
      };
    case "appShell/completeWorkflowRun":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          actionStates: {
            ...state.workflowRun.actionStates,
            [action.completion.key]: action.completion.actionState,
          },
          badges: {
            ...state.workflowRun.badges,
            [action.completion.key]: action.completion.badge,
          },
          timestamps: {
            ...state.workflowRun.timestamps,
            [action.completion.key]: action.completion.timestamp,
          },
        },
      };
    case "appShell/resetWorkflowOnSourceChange": {
      const resetState = computeSourceChangeConsequences(
        { ree: buildReeViewFromState(state) },
        action.workflowParams,
      );
      const split = splitReeViewState(resetState.ree);
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          reeSpec: split.reeSpec,
          workspaceSourceState: split.workspaceSourceState,
          artifactStatus: split.artifactStatus,
          sourceSnapshotArchiveName: resetState.sourceSnapshotArchiveName,
        },
        workflowRun: {
          ...state.workflowRun,
          evaluationState: split.evaluationState,
          actionStates: resetState.actionStates,
          badges: resetState.badges,
          timestamps: resetState.timestamps,
          workflowParams: resetState.workflowParams,
        },
      };
    }
    default:
      return state;
  }
}

export function AppShellProvider({ children, initialRee }: AppShellProviderProps) {
  const [state, dispatch] = useReducer(
    appShellReducer,
    initialRee ?? createEmptyReeViewState(),
    createInitialState,
  );

  const value = useMemo(
    () => ({
      state,
      dispatch,
    }),
    [state],
  );

  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShellContext(): AppShellContextValue {
  const ctx = useContext(AppShellContext);
  if (!ctx) {
    throw new Error("useAppShellContext must be used within AppShellProvider");
  }
  return ctx;
}
