import type {
  ExplorerAction,
  ExplorerState,
  ExplorerStateUpdater,
  ServiceRunCompletionPayload,
  SourceOutcomePayload,
  WorkspaceHydrationPayload,
} from "../application/explorer/explorerState";

export type StateUpdater<T> = ExplorerStateUpdater<T>;
export type AppAction = ExplorerAction;

export interface AppContextState {
  explorer: ExplorerState;
}

export type {
  ExplorerState,
  ServiceRunCompletionPayload,
  SourceOutcomePayload,
  WorkspaceHydrationPayload,
};
