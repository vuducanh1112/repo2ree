import type { ReeFile } from "../ree/ReeTypes";

export interface WorkspaceBinaryDownload {
  bytes: ArrayBuffer;
  fileName?: string;
}

export interface ReeProject<TFile = unknown, TRee = unknown> {
  id: string;
  files: TFile[];
  reeFiles?: ReeFile[];
  ree?: TRee;
}
