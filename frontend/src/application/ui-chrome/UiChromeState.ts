import type { ToastState } from "../workflow/WorkflowStepTypes";
import type { WorkspaceEditorPage } from "../workspace-editor/WorkspaceEditorPages";
import { PAGE } from "../workspace-editor/WorkspaceEditorPages";

export type UiChromeStateUpdater<T> = T | ((previous: T) => T);

export interface UiChromeState {
  toast: ToastState | null;
  page: WorkspaceEditorPage;
  focusedField: string | null;
  navCollapsed: boolean;
  showReviewPreview: boolean;
}

export function resolveUiChromeUpdater<T>(previous: T, updater: UiChromeStateUpdater<T>): T {
  if (typeof updater === "function") {
    return (updater as (value: T) => T)(previous);
  }
  return updater;
}

export function createInitialUiChromeState(): UiChromeState {
  return {
    toast: null,
    page: PAGE.SOURCE,
    focusedField: null,
    navCollapsed: false,
    showReviewPreview: false,
  };
}
