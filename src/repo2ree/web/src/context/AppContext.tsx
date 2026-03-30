import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import { APP_PAGE, PAGE } from "../constants/pages";
import { initialServiceParams } from "../constants/services";
import { normalizeExplorerPage } from "../features/explorer/utils/navigation";
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
    appPage: APP_PAGE.LANDING,
    explorer: {
      ree: initialExplorerRee,
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
      immutableSourceSnapshotFiles: [],
      immutableSourceSnapshotArchiveName: "",
      showReviewerPreview: false,
    },
  };
}

function appReducer(state: AppContextState, action: AppAction): AppContextState {
  switch (action.type) {
    case ACTION_TYPES.app.setPage: {
      return { ...state, appPage: resolveUpdater(state.appPage, action.page) };
    }
    case ACTION_TYPES.explorer.setRee: {
      return {
        ...state,
        explorer: { ...state.explorer, ree: resolveUpdater(state.explorer.ree, action.ree) },
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
    case ACTION_TYPES.explorer.resetWorkflowOnSourceChange: {
      return {
        ...state,
        explorer: {
          ...state.explorer,
          badges: {},
          timestamps: {},
          serviceLogs: {},
          actionStates: {},
          serviceParams: action.serviceParams,
          ree: {
            ...state.explorer.ree,
            runtime: "",
            build_runtime_script: "",
            activation_script: "",
            sbom: "",
            swhid: "",
            detected_dependencies: "",
            repro_level: "",
            _evalLevel: 0,
            _sourceAvailable: false,
            _sourceAcquiredBy: undefined,
            _runtimeIncluded: false,
            zenodo_doi: "",
            _uploadedArchive: "",
            _sourceSnapshotArchive: "",
            _sourceSnapshotCapturedAt: "",
          },
          virtualFiles: [],
          immutableSourceSnapshotFiles: [],
          immutableSourceSnapshotArchiveName: "",
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
