import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import {
  applyExplorerAction,
  createInitialExplorerState,
} from "../application/explorer/explorerState";
import type { Ree } from "../types";
import type { AppAction, AppContextState } from "./types";

interface AppContextValue {
  state: AppContextState;
  dispatch: React.Dispatch<AppAction>;
}

const AppContext = createContext<AppContextValue | null>(null);

interface AppProviderProps {
  children: ReactNode;
  initialExplorerRee: Ree;
}

function createInitialState(initialExplorerRee: Ree): AppContextState {
  return {
    explorer: createInitialExplorerState(initialExplorerRee),
  };
}

function appReducer(state: AppContextState, action: AppAction): AppContextState {
  return {
    ...state,
    explorer: applyExplorerAction(state.explorer, action),
  };
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
