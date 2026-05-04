import type { AppShellPage } from "../app-shell/AppShellPages";
import { PAGE } from "../app-shell/AppShellPages";
import type { ToastState } from "../workflow/WorkflowStepTypes";

export interface UiChromeState {
  toast: ToastState | null;
  page: AppShellPage;
  focusedField: string | null;
  navCollapsed: boolean;
  showReviewPreview: boolean;
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
