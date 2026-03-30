import type { AppPage } from "../types";
import type { AppContextState, ExplorerState } from "./types";

export const appSelectors = {
  page: (state: AppContextState): AppPage => state.appPage,
};

export const explorerSelectors = {
  state: (state: AppContextState): ExplorerState => state.explorer,
};
