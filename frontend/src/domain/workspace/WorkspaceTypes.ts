import type { ReeFile } from "../ree/ReeTypes";
import type { ReeViewState } from "../ree/ReeViewState";

export interface WorkspaceBinaryDownload {
  bytes: ArrayBuffer;
  fileName?: string;
}

export interface ReeProject<TFile = unknown> {
  id: string;
  files: TFile[];
  reeFiles?: ReeFile[];
  ree?: ReeViewState;
}
