import type { AppPage, Ree, ToastState } from "../types";

export interface AppState {
  currentPage: AppPage;
  currentRee: Ree | null;
  toast: ToastState | null;
  loadingByKey: Record<string, boolean>;
}

export type AppAction =
  | { type: "setPage"; page: AppPage }
  | { type: "setRee"; ree: Ree | null }
  | { type: "showToast"; toast: ToastState }
  | { type: "hideToast" }
  | { type: "setLoading"; key: string; loading: boolean };

export const initialAppState: AppState = {
  currentPage: "landing",
  currentRee: null,
  toast: null,
  loadingByKey: {},
};
