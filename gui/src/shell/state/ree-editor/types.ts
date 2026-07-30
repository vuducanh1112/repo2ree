import type { ToastState } from "@core/ree-steps/stepTypes";

export type ShowToast = (message: string, type?: ToastState["type"]) => void;
