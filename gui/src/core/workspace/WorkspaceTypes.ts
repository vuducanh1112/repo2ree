import type { ReceiptView } from "../receipts/authorReceipts";
import type { ReeFile } from "../ree/ReeTypes";

export interface WorkspaceBinaryDownload {
  bytes: ArrayBuffer;
  fileName?: string;
}

// Display-ready source-repository facts, computed by the backend
// (repo2ree_core.source_repo) and passed through untouched. The GUI never
// re-derives these — it only renders them.
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
  /** Author evidence parsed from the portable REE document. */
  authorReceipts?: ReceiptView[];
  sourceRepo?: SourceRepoMetadata;
  /** The image this REE's workbench was provisioned from. */
  workbenchImage?: string;
}
