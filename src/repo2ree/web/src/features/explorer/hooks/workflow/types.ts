import type { ToastState } from "../../../../types";

export type ShowToast = (msg: string, type?: ToastState["type"]) => void;
