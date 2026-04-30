import type { ToastState } from "../../../application/workflow/WorkflowStepTypes";

export type ShowToast = (msg: string, type?: ToastState["type"]) => void;
