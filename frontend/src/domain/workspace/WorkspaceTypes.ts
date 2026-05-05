import type { ReeFile } from "../ree/ReeTypes";
import type { ReeView } from "../ree/ReeView";

export interface WorkspaceBinaryDownload {
  bytes: ArrayBuffer;
  fileName?: string;
}

export interface ReeProject<TFile = unknown> {
  id: string;
  files: TFile[];
  reeFiles?: ReeFile[];
  ree?: ReeView;
}
