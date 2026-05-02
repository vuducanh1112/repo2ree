import type { AppShellPage } from "../app-shell/AppShellPages";
import { PAGE } from "../app-shell/AppShellPages";
import type { ToastState } from "../workflow/WorkflowStepTypes";

export type UiChromeStateUpdater<T> = T | ((previous: T) => T);

export interface UiChromeState {
  toast: ToastState | null;
  page: AppShellPage;
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
