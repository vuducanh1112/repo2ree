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
import { createEmptyRee, type Ree } from "../../../domain/ree/ReeSpec";
import { computeSourceChangeConsequences } from "../../../domain/workspace/sourceChangeConsequences";

interface WorkspaceShellContextValue {
  state: WorkspaceShellContextState;
  dispatch: React.Dispatch<WorkspaceShellAction>;
}

const WorkspaceShellContext = createContext<WorkspaceShellContextValue | null>(null);

interface WorkspaceShellProviderProps {
  children: ReactNode;
  initialWorkspaceShellRee?: Ree;
}

export function createInitialState(
  initialWorkspaceShellRee: Ree = createEmptyRee(),
): WorkspaceShellContextState {
  return {
    workspaceDraft: createInitialWorkspaceDraftState(initialWorkspaceShellRee),
    workspaceRemote: createInitialWorkspaceRemoteState(),
    workflowRun: createInitialWorkflowRunState(),
    uiChrome: createInitialUiChromeState(),
  };
}

export function workspaceShellReducer(
  state: WorkspaceShellContextState,
  action: WorkspaceShellAction,
): WorkspaceShellContextState {
  switch (action.type) {
    case "workspaceShell/setRee":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          ree: enforceSourceOriginRules(
            resolveWorkspaceDraftUpdater(state.workspaceDraft.ree, action.ree),
          ),
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
          ree: action.workspace.ree
            ? enforceSourceOriginRules(action.workspace.ree)
            : state.workspaceDraft.ree,
        },
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceFiles: action.workspace.workspaceFiles,
          reeArtifactFiles: action.workspace.reeArtifactFiles,
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
    case "workspaceShell/applySourcePatchOutcome":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          ree: enforceSourceOriginRules({
            ...state.workspaceDraft.ree,
            ...action.outcome.reePatch,
          }),
        },
        workspaceRemote: {
          ...state.workspaceRemote,
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
        { ree: state.workspaceDraft.ree },
        action.workflowParams,
      );
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          ree: resetState.ree,
        },
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceFiles: resetState.workspaceFiles,
          reeArtifactFiles: resetState.reeArtifactFiles,
          sourceSnapshotFiles: resetState.sourceSnapshotFiles,
          sourceSnapshotArchiveName: resetState.sourceSnapshotArchiveName,
        },
        workflowRun: {
          ...state.workflowRun,
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

export function WorkspaceShellProvider({
  children,
  initialWorkspaceShellRee,
}: WorkspaceShellProviderProps) {
  const [state, dispatch] = useReducer(
    workspaceShellReducer,
    initialWorkspaceShellRee ?? createEmptyRee(),
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
