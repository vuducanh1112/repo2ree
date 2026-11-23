import type { ReceiptView } from "../receipts/authorReceipts";
import type { ReeFile } from "../ree/ReeTypes";

export interface WorkspaceBinaryDownload {
  bytes: ArrayBuffer;
  fileName?: string;
}

export interface SourceRepoMetadata {
  name: string;
  origin: string;
  acquiredBy: string;
  sourceType: string;
  swhid: string;
  sizeBytes: number | null;
  sizeLabel: string | null;
}

export interface ReeProject<TFile = unknown, TRee = unknown> {
  id: string;
  files: TFile[];
  reeFiles?: ReeFile[];
  ree?: TRee;
  authorReceipts?: ReceiptView[];
  sourceRepo?: SourceRepoMetadata;
  storeId?: string;
  workbenchLocation?: string;
}
