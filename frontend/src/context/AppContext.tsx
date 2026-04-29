import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import { normalizeExplorerPage } from "../application/explorer/navigation";
import { PAGE } from "../constants/pages";
import { initialServiceParams } from "../constants/services";
import { enforceSourceOriginContract } from "../domain/ree/sourceContract";
import { computeExplorerSourceChangeReset } from "../domain/workflow/sourceChangeReset";
import type { Ree } from "../types";
import { ACTION_TYPES } from "./actionTypes";
import type { AppAction, AppContextState, StateUpdater } from "./types";

interface AppContextValue {
  state: AppContextState;
  dispatch: React.Dispatch<AppAction>;
}

const AppContext = createContext<AppContextValue | null>(null);

interface AppProviderProps {
  children: ReactNode;
  initialExplorerRee: Ree;
}

function resolveUpdater<T>(previous: T, updater: StateUpdater<T>): T {
  if (typeof updater === "function") {
    return (updater as (value: T) => T)(previous);
  }
  return updater;
}

function createInitialState(initialExplorerRee: Ree): AppContextState {
  return {
    explorer: {
      ree: enforceSourceOriginContract(initialExplorerRee),
      locked: false,
      repoMode: "url",
      actionStates: {},
      badges: {},
      timestamps: {},
      serviceLogs: {},
      serviceParams: initialServiceParams(),
      toast: null,
      page: PAGE.SOURCE,
      focusedField: null,
      navCollapsed: false,
      virtualFiles: [],
      workspaceReeFiles: [],
      immutableSourceSnapshotFiles: [],
      immutableSourceSnapshotArchiveName: "",
      showReviewerPreview: false,
    },
  };
}

function appReducer(state: AppContextState, action: AppAction): AppContextState {
  switch (action.type) {
    case ACTION_TYPES.explorer.setRee: {
      const nextRee = enforceSourceOriginContract(resolveUpdater(state.explorer.ree, action.ree));
      return {
        ...state,
        explorer: { ...state.explorer, ree: nextRee },
      };
    }
    case ACTION_TYPES.explorer.setLocked: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          locked: resolveUpdater(state.explorer.locked, action.locked),
        },
      };
    }
    case ACTION_TYPES.explorer.setRepoMode: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          repoMode: resolveUpdater(state.explorer.repoMode, action.repoMode),
        },
      };
    }
    case ACTION_TYPES.explorer.setActionStates: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          actionStates: resolveUpdater(state.explorer.actionStates, action.actionStates),
        },
      };
    }
    case ACTION_TYPES.explorer.setBadges: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          badges: resolveUpdater(state.explorer.badges, action.badges),
        },
      };
    }
    case ACTION_TYPES.explorer.setTimestamps: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          timestamps: resolveUpdater(state.explorer.timestamps, action.timestamps),
        },
      };
    }
    case ACTION_TYPES.explorer.setServiceLogs: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          serviceLogs: resolveUpdater(state.explorer.serviceLogs, action.serviceLogs),
        },
      };
    }
    case ACTION_TYPES.explorer.setServiceParams: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          serviceParams: resolveUpdater(state.explorer.serviceParams, action.serviceParams),
        },
      };
    }
    case ACTION_TYPES.explorer.setToast: {
      return {
        ...state,
        explorer: { ...state.explorer, toast: resolveUpdater(state.explorer.toast, action.toast) },
      };
    }
    case ACTION_TYPES.explorer.setPage: {
      const candidate = resolveUpdater(state.explorer.page, action.page);
      return {
        ...state,
        explorer: {
          ...state.explorer,
          page: normalizeExplorerPage(candidate, state.explorer.page),
        },
      };
    }
    case ACTION_TYPES.explorer.setFocusedField: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          focusedField: resolveUpdater(state.explorer.focusedField, action.focusedField),
        },
      };
    }
    case ACTION_TYPES.explorer.setNavCollapsed: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          navCollapsed: resolveUpdater(state.explorer.navCollapsed, action.navCollapsed),
        },
      };
    }
    case ACTION_TYPES.explorer.setVirtualFiles: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          virtualFiles: resolveUpdater(state.explorer.virtualFiles, action.virtualFiles),
        },
      };
    }
    case ACTION_TYPES.explorer.setWorkspaceReeFiles: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          workspaceReeFiles: resolveUpdater(
            state.explorer.workspaceReeFiles,
            action.workspaceReeFiles,
          ),
        },
      };
    }
    case ACTION_TYPES.explorer.hydrateWorkspace: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          virtualFiles: action.workspace.virtualFiles,
          workspaceReeFiles: action.workspace.workspaceReeFiles,
          ree: action.workspace.ree
            ? enforceSourceOriginContract(action.workspace.ree)
            : state.explorer.ree,
        },
      };
    }
    case ACTION_TYPES.explorer.setImmutableSourceSnapshotFiles: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          immutableSourceSnapshotFiles: resolveUpdater(
            state.explorer.immutableSourceSnapshotFiles,
            action.immutableSourceSnapshotFiles,
          ),
        },
      };
    }
    case ACTION_TYPES.explorer.setImmutableSourceSnapshotArchiveName: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          immutableSourceSnapshotArchiveName: resolveUpdater(
            state.explorer.immutableSourceSnapshotArchiveName,
            action.immutableSourceSnapshotArchiveName,
          ),
        },
      };
    }
    case ACTION_TYPES.explorer.applySourceOutcome: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          ree: enforceSourceOriginContract(action.outcome.ree),
          immutableSourceSnapshotFiles: action.outcome.immutableSourceSnapshotFiles,
          immutableSourceSnapshotArchiveName: action.outcome.immutableSourceSnapshotArchiveName,
          actionStates: action.outcome.actionState
            ? { ...state.explorer.actionStates, source: action.outcome.actionState }
            : state.explorer.actionStates,
          badges:
            typeof action.outcome.badge === "boolean"
              ? { ...state.explorer.badges, source: action.outcome.badge }
              : state.explorer.badges,
          timestamps: action.outcome.timestamp
            ? { ...state.explorer.timestamps, source: action.outcome.timestamp }
            : state.explorer.timestamps,
        },
      };
    }
    case ACTION_TYPES.explorer.setShowReviewerPreview: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          showReviewerPreview: resolveUpdater(
            state.explorer.showReviewerPreview,
            action.showReviewerPreview,
          ),
        },
      };
    }
    case ACTION_TYPES.explorer.completeServiceRun: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          serviceLogs: {
            ...state.explorer.serviceLogs,
            [action.completion.key]: action.completion.serviceLog,
          },
          actionStates: {
            ...state.explorer.actionStates,
            [action.completion.key]: action.completion.actionState,
          },
          badges: {
            ...state.explorer.badges,
            [action.completion.key]: action.completion.badge,
          },
          timestamps: {
            ...state.explorer.timestamps,
            [action.completion.key]: action.completion.timestamp,
          },
        },
      };
    }
    case ACTION_TYPES.explorer.resetWorkflowOnSourceChange: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          ...computeExplorerSourceChangeReset(state.explorer, action.serviceParams),
        },
      };
    }
    default:
      return state;
  }
}

export function AppProvider({ children, initialExplorerRee }: AppProviderProps) {
  const [state, dispatch] = useReducer(appReducer, initialExplorerRee, createInitialState);

  const value = useMemo(
    () => ({
      state,
      dispatch,
    }),
    [state],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error("useAppContext must be used within AppProvider");
  }
  return ctx;
}
