import type { AppContextState, ExplorerState } from "./types";

export const explorerSelectors = {
  state: (state: AppContextState): ExplorerState => state.explorer,
};
