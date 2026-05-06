import type { ToastState } from "../../application/ree-assembly/assemblyStepTypes";

export type ShowToast = (message: string, type?: ToastState["type"]) => void;
