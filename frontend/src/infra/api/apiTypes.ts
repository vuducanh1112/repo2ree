export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface ApiListResponse<TItem> {
  items: TItem[];
  nextCursor?: string;
}

export interface ReeSummaryDto {
  reeId: string;
  externalRef?: string;
  name: string;
  status: "draft" | "ready" | "sealed" | "archived";
  createdAt: string;
  updatedAt: string;
}

export interface ReeFileDto {
  path: string;
  content?: string;
  size?: number;
  kind: "source" | "generated";
  etag?: string;
}

export interface ReeArtifactFileDto {
  path: string;
  content?: string;
  size?: number;
  kind: "ree";
  tag?: string;
}

export interface ReeDraftDto {
  name: string;
  origin_url: string;
  source_type: string;
  runtime: string;
  sbom: string;
  build_runtime_script: string;
  activation_script: string;
  swhid: string;
  zenodo_doi: string;
  dataverse_doi: string;
  repro_level: string;
  detected_dependencies: string;
  hardware_description: Record<string, unknown>;
  _sealedAt: string;
  _sealHash: string;
  _evalLevel: number;
  _sourceIncluded: boolean;
  _sourceAvailable: boolean;
  _sourceAcquiredBy: string;
  _uploadedArchive: string;
  _sourceSnapshotArchive: string;
  _sourceSnapshotCapturedAt: string;
  _runtimeIncluded: boolean;
  _downloadableFiles: string[];
}

export interface ReeDetailDto extends ReeSummaryDto {
  reeDraft: Partial<ReeDraftDto>;
  files?: ReeFileDto[];
  reeFiles?: ReeArtifactFileDto[];
}

export interface CreateReeRequestDto {
  sourceMode: "url" | "upload" | "demo";
  originUrl?: string;
  sourceType?: "git" | "tarball" | "zip";
  name?: string;
}

export interface PatchReeRequestDto {
  reePatch: Partial<ReeDraftDto>;
  expectedVersion?: string;
}

export interface SourceAcquireRequestDto {
  originUrl: string;
  sourceType: "git" | "tarball" | "zip";
}

export interface UploadInitRequestDto {
  fileName: string;
  size: number;
  contentType: string;
}

export interface UploadInitResponseDto {
  uploadUrl: string;
  uploadToken: string;
  expiresAt: string;
}

export interface ReviewUploadInitRequestDto {
  fileName: string;
  size: number;
  contentType: string;
}

export interface ReviewUploadInitResponseDto {
  reviewId: string;
  uploadUrl: string;
  uploadToken: string;
  expiresAt: string;
}

export interface ReviewUploadCompleteRequestDto {
  uploadToken: string;
  archiveName: string;
}

export interface ReviewDetailDto {
  reviewId: string;
  name: string;
  status: "uploading" | "ready";
  createdAt: string;
  updatedAt: string;
  archiveName?: string;
  reeDraft: Partial<ReeDraftDto>;
  files?: Array<{ path: string; size?: number }>;
  // wire-format field name: backend uses workspaceFiles for the file listing of an REE.
  workspaceFiles?: Array<{ path: string; size?: number }>;
}

export interface ReviewUploadCompleteResponseDto {
  status: "ready";
  review: ReviewDetailDto;
}

export type WorkflowOperationDto =
  | "evaluate"
  | "build"
  | "hbom"
  | "sbom"
  | "activation"
  | "source"
  | "swh"
  | "zenodo"
  | "dataverse";

export type WorkflowRunStatusDto =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

export interface CreateBuildRuntimeRunRequestDto {
  build_runtime_script_path: string;
  produced_runtime_path: string;
  idempotencyKey?: string;
}

export interface CreateGenerateSbomRunRequestDto {
  produced_runtime_path: string;
  idempotencyKey?: string;
}

export interface CreateGenerateHbomRunRequestDto {
  idempotencyKey?: string;
}

export interface CreateActivationTestRunRequestDto {
  activation_script_path: string;
  idempotencyKey?: string;
}

export interface CreateEvaluateRunRequestDto {
  strict: boolean;
  swhid_check: boolean;
  idempotencyKey?: string;
}

export interface WorkflowRunDto {
  runId: string;
  reeId: string;
  operation: WorkflowOperationDto;
  status: WorkflowRunStatusDto;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  outputs?: Record<string, unknown>;
}

export interface WorkflowLogEntryDto {
  seq: number;
  ts: string;
  stream: "stdout" | "stderr" | "system";
  level: "info" | "warn" | "error" | "debug";
  message: string;
}

export interface WorkflowLogsDto {
  entries: WorkflowLogEntryDto[];
  nextCursor?: string;
  hasMore: boolean;
  runStatus: WorkflowRunStatusDto;
}
