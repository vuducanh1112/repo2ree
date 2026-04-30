import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import {
  createInitialUiChromeState,
  resolveUiChromeUpdater,
} from "../../../application/ui-chrome/UiChromeState";
import {
  createInitialWorkflowRunState,
  resolveWorkflowRunUpdater,
} from "../../../application/workflow-runs/WorkflowRunState";
import {
  createInitialWorkspaceDraftState,
  resolveWorkspaceDraftUpdater,
} from "../../../application/workspace-draft/WorkspaceDraftState";
import {
  createInitialWorkspaceRemoteState,
  resolveWorkspaceRemoteUpdater,
} from "../../../application/workspace-remote/WorkspaceRemoteState";
import { normalizeUiChromePage } from "../../../application/workspace-shell/WorkspaceShellState";
import type {
  WorkspaceShellAction,
  WorkspaceShellContextState,
} from "../../../application/workspace-shell/WorkspaceShellTypes";
import { enforceSourceOriginRules } from "../../../domain/artifact/sourceOriginRules";
import type { ReeDraftViewModel } from "../../../domain/ree/ReeSpec";
import {
  createEmptyReeDraftViewModel,
  splitReeDraftViewModel,
  toReeDraftViewModel,
} from "../../../domain/ree/reeDraftViewModel";
import { computeSourceChangeConsequences } from "../../../domain/workspace/sourceChangeConsequences";

interface WorkspaceShellContextValue {
  state: WorkspaceShellContextState;
  dispatch: React.Dispatch<WorkspaceShellAction>;
}

const WorkspaceShellContext = createContext<WorkspaceShellContextValue | null>(null);

interface WorkspaceShellProviderProps {
  children: ReactNode;
  initialRee?: ReeDraftViewModel;
}

export function createInitialState(
  initialRee: ReeDraftViewModel = createEmptyReeDraftViewModel(),
): WorkspaceShellContextState {
  const normalizedRee = enforceSourceOriginRules(initialRee);
  const split = splitReeDraftViewModel(normalizedRee);
  return {
    workspaceDraft: createInitialWorkspaceDraftState(normalizedRee),
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

function buildReeDraftFromState(state: WorkspaceShellContextState): ReeDraftViewModel {
  return toReeDraftViewModel({
    reeSpec: state.workspaceDraft.reeSpec,
    workspaceSourceState: state.workspaceRemote.workspaceSourceState,
    artifactStatus: state.workspaceRemote.artifactStatus,
    evaluationState: state.workflowRun.evaluationState,
  });
}

export function workspaceShellReducer(
  state: WorkspaceShellContextState,
  action: WorkspaceShellAction,
): WorkspaceShellContextState {
  switch (action.type) {
    case "workspaceShell/setRee": {
      const nextRee = enforceSourceOriginRules(
        resolveWorkspaceDraftUpdater(buildReeDraftFromState(state), action.ree),
      );
      const split = splitReeDraftViewModel(nextRee);
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
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
    case "workspaceShell/setReeSpec":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          reeSpec: resolveWorkspaceDraftUpdater(state.workspaceDraft.reeSpec, action.reeSpec),
        },
      };
    case "workspaceShell/setLocked":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          locked: resolveWorkspaceDraftUpdater(state.workspaceDraft.locked, action.locked),
        },
      };
    case "workspaceShell/setRepoMode":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          repoMode: resolveWorkspaceDraftUpdater(state.workspaceDraft.repoMode, action.repoMode),
        },
      };
    case "workspaceShell/setWorkspaceSourceState":
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
    case "workspaceShell/setArtifactStatus":
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
    case "workspaceShell/setActionStates":
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
    case "workspaceShell/setBadges":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          badges: resolveWorkflowRunUpdater(state.workflowRun.badges, action.badges),
        },
      };
    case "workspaceShell/setTimestamps":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          timestamps: resolveWorkflowRunUpdater(state.workflowRun.timestamps, action.timestamps),
        },
      };
    case "workspaceShell/setWorkflowLogs":
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
    case "workspaceShell/setWorkflowParams":
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
    case "workspaceShell/setEvaluationState":
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
    case "workspaceShell/setToast":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          toast: resolveUiChromeUpdater(state.uiChrome.toast, action.toast),
        },
      };
    case "workspaceShell/setPage": {
      const candidate = resolveUiChromeUpdater(state.uiChrome.page, action.page);
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          page: normalizeUiChromePage(candidate, state.uiChrome.page),
        },
      };
    }
    case "workspaceShell/setFocusedField":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          focusedField: resolveUiChromeUpdater(state.uiChrome.focusedField, action.focusedField),
        },
      };
    case "workspaceShell/setNavCollapsed":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          navCollapsed: resolveUiChromeUpdater(state.uiChrome.navCollapsed, action.navCollapsed),
        },
      };
    case "workspaceShell/setWorkspaceFiles":
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
    case "workspaceShell/setReeArtifactFiles":
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
    case "workspaceShell/hydrateWorkspace":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          reeSpec: action.workspace.reeSpec ?? state.workspaceDraft.reeSpec,
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
    case "workspaceShell/setSourceSnapshotFiles":
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
    case "workspaceShell/setSourceSnapshotArchiveName":
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
    case "workspaceShell/applySourceOutcome":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          reeSpec: action.outcome.reeSpecPatch
            ? {
                ...state.workspaceDraft.reeSpec,
                ...action.outcome.reeSpecPatch,
              }
            : state.workspaceDraft.reeSpec,
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
    case "workspaceShell/setShowReviewPreview":
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
    case "workspaceShell/completeWorkflowRun":
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
    case "workspaceShell/resetWorkflowOnSourceChange": {
      const resetState = computeSourceChangeConsequences(
        { ree: buildReeDraftFromState(state) },
        action.workflowParams,
      );
      const split = splitReeDraftViewModel(resetState.ree);
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
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

export function WorkspaceShellProvider({ children, initialRee }: WorkspaceShellProviderProps) {
  const [state, dispatch] = useReducer(
    workspaceShellReducer,
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

  return <WorkspaceShellContext.Provider value={value}>{children}</WorkspaceShellContext.Provider>;
}

export function useWorkspaceShellContext(): WorkspaceShellContextValue {
  const ctx = useContext(WorkspaceShellContext);
  if (!ctx) {
    throw new Error("useWorkspaceShellContext must be used within WorkspaceShellProvider");
  }
  return ctx;
}
