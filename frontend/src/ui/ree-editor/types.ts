import type { ToastState } from "../../core/ree-assembly/assemblyStepTypes";

export type ShowToast = (message: string, type?: ToastState["type"]) => void;
