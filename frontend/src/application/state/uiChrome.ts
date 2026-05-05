import type { ToastState } from "../workflow/WorkflowStepTypes";
import type { AppShellPage } from "./pages";
import { PAGE } from "./pages";

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
