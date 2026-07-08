import type { ReeFile } from "../ree/ReeTypes";
import type { ConsistencyReport } from "../ree-assembly/sealConsistency";

export interface WorkspaceBinaryDownload {
  bytes: ArrayBuffer;
  fileName?: string;
}

// Display-ready source-repository facts, computed by the backend
// (repo2ree_core.source_repo) and passed through untouched. The frontend never
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

export type DraftManifest = Record<string, unknown>;

export interface ReeProject<TFile = unknown, TRee = unknown> {
  id: string;
  files: TFile[];
  reeFiles?: ReeFile[];
  ree?: TRee;
  draftManifest?: DraftManifest;
  sourceRepo?: SourceRepoMetadata;
  /** Per-step freshness of recorded run receipts vs. the current tree. */
  consistency?: ConsistencyReport;
  /** The image this REE's workbench was provisioned from. */
  workbenchImage?: string;
}
