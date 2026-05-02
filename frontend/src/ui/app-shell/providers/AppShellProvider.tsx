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
import {
  createInitialWorkspaceRemoteState,
  resolveWorkspaceRemoteUpdater,
} from "../../../application/workspace-remote/WorkspaceRemoteState";
import { enforceSourceOriginRules } from "../../../domain/artifact/sourceOriginRules";
import type { ReeDraftViewModel } from "../../../domain/ree/ReeSpec";
import {
  createEmptyReeDraftViewModel,
  splitReeDraftViewModel,
  toReeDraftViewModel,
} from "../../../domain/ree/reeDraftViewModel";
import { computeSourceChangeConsequences } from "../../../domain/workspace/sourceChangeConsequences";

interface AppShellContextValue {
  state: AppShellContextState;
  dispatch: React.Dispatch<AppShellAction>;
}

const AppShellContext = createContext<AppShellContextValue | null>(null);

interface AppShellProviderProps {
  children: ReactNode;
  initialRee?: ReeDraftViewModel;
}

export function createInitialState(
  initialRee: ReeDraftViewModel = createEmptyReeDraftViewModel(),
): AppShellContextState {
  const normalizedRee = enforceSourceOriginRules(initialRee);
  const split = splitReeDraftViewModel(normalizedRee);
  return {
    reeDraft: createInitialReeDraftState(normalizedRee),
    workspaceRemote: {
      ...createInitialWorkspaceRemoteState(),
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

function buildReeDraftFromState(state: AppShellContextState): ReeDraftViewModel {
  return toReeDraftViewModel({
    reeSpec: state.reeDraft.reeSpec,
    workspaceSourceState: state.workspaceRemote.workspaceSourceState,
    artifactStatus: state.workspaceRemote.artifactStatus,
    evaluationState: state.workflowRun.evaluationState,
  });
}

export function appShellReducer(
  state: AppShellContextState,
  action: AppShellAction,
): AppShellContextState {
  switch (action.type) {
    case "appShell/setRee": {
      const nextRee = enforceSourceOriginRules(
        resolveReeDraftUpdater(buildReeDraftFromState(state), action.ree),
      );
      const split = splitReeDraftViewModel(nextRee);
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          reeSpec: split.reeSpec,
        },
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceSourceState: split.workspaceSourceState,
          artifactStatus: split.artifactStatus,
        },
        workflowRun: {
          ...state.workflowRun,
          evaluationState: split.evaluationState,
        },
      };
    }
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
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceSourceState: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.workspaceSourceState,
            action.workspaceSourceState,
          ),
        },
      };
    case "appShell/setArtifactStatus":
      return {
        ...state,
        workspaceRemote: {
          ...state.workspaceRemote,
          artifactStatus: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.artifactStatus,
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
    case "appShell/setWorkflowLogs":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          workflowLogs: resolveWorkflowRunUpdater(
            state.workflowRun.workflowLogs,
            action.workflowLogs,
          ),
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
    case "appShell/setWorkspaceFiles":
      return {
        ...state,
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceFiles: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.workspaceFiles,
            action.workspaceFiles,
          ),
        },
      };
    case "appShell/setReeArtifactFiles":
      return {
        ...state,
        workspaceRemote: {
          ...state.workspaceRemote,
          reeArtifactFiles: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.reeArtifactFiles,
            action.reeArtifactFiles,
          ),
        },
      };
    case "appShell/hydrateWorkspace":
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          reeSpec: action.workspace.reeSpec ?? state.reeDraft.reeSpec,
        },
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceFiles: action.workspace.workspaceFiles,
          reeArtifactFiles: action.workspace.reeArtifactFiles,
          workspaceSourceState:
            action.workspace.workspaceSourceState ?? state.workspaceRemote.workspaceSourceState,
          artifactStatus: action.workspace.artifactStatus ?? state.workspaceRemote.artifactStatus,
        },
        workflowRun: {
          ...state.workflowRun,
          evaluationState: action.workspace.evaluationState ?? state.workflowRun.evaluationState,
        },
      };
    case "appShell/setSourceSnapshotFiles":
      return {
        ...state,
        workspaceRemote: {
          ...state.workspaceRemote,
          sourceSnapshotFiles: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.sourceSnapshotFiles,
            action.sourceSnapshotFiles,
          ),
        },
      };
    case "appShell/setSourceSnapshotArchiveName":
      return {
        ...state,
        workspaceRemote: {
          ...state.workspaceRemote,
          sourceSnapshotArchiveName: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.sourceSnapshotArchiveName,
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
        },
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceSourceState: action.outcome.workspaceSourceState
            ? {
                ...state.workspaceRemote.workspaceSourceState,
                ...action.outcome.workspaceSourceState,
              }
            : state.workspaceRemote.workspaceSourceState,
          sourceSnapshotFiles: action.outcome.sourceSnapshotFiles,
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
          workflowLogs: {
            ...state.workflowRun.workflowLogs,
            [action.completion.key]: action.completion.workflowLog,
          },
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
        { ree: buildReeDraftFromState(state) },
        action.workflowParams,
      );
      const split = splitReeDraftViewModel(resetState.ree);
      return {
        ...state,
        reeDraft: {
          ...state.reeDraft,
          reeSpec: split.reeSpec,
        },
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceSourceState: split.workspaceSourceState,
          artifactStatus: split.artifactStatus,
          workspaceFiles: resetState.workspaceFiles,
          reeArtifactFiles: resetState.reeArtifactFiles,
          sourceSnapshotFiles: resetState.sourceSnapshotFiles,
          sourceSnapshotArchiveName: resetState.sourceSnapshotArchiveName,
        },
        workflowRun: {
          ...state.workflowRun,
          evaluationState: split.evaluationState,
          actionStates: resetState.actionStates,
          badges: resetState.badges,
          timestamps: resetState.timestamps,
          workflowLogs: resetState.workflowLogs,
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
    initialRee ?? createEmptyReeDraftViewModel(),
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
