import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import type { AppAction, AppState } from "./types";
import { initialAppState } from "./types";

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "setPage":
      return { ...state, currentPage: action.page };
    case "setRee":
      return { ...state, currentRee: action.ree };
    case "showToast":
      return { ...state, toast: action.toast };
    case "hideToast":
      return { ...state, toast: null };
    case "setLoading":
      return {
        ...state,
        loadingByKey: {
          ...state.loadingByKey,
          [action.key]: action.loading,
        },
      };
    default:
      return state;
  }
}

interface AppContextValue {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

const AppContext = createContext<AppContextValue | null>(null);

interface AppProviderProps {
  children: ReactNode;
}

export function AppProvider({ children }: AppProviderProps) {
  const [state, dispatch] = useReducer(appReducer, initialAppState);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error("useAppContext must be used within AppProvider");
  }
  return ctx;
}
