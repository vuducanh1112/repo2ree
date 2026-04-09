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

export interface WorkspaceSummaryDto {
  workspaceId: string;
  externalRef?: string;
  name: string;
  status: "draft" | "ready" | "sealed" | "archived";
  createdAt: string;
  updatedAt: string;
}

export interface WorkspaceFileDto {
  path: string;
  content?: string;
  size?: number;
  kind: "source" | "generated";
  etag?: string;
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
  hardware_description: Record<string, unknown>;
  _sealedAt: string;
  _sealHash: string;
  _evalLevel: number;
  _sourceIncluded: boolean;
  _sourceAvailable: boolean;
  _sourceAcquiredBy: string;
  _sourceSnapshotArchive: string;
  _sourceSnapshotCapturedAt: string;
  _runtimeIncluded: boolean;
}

export interface WorkspaceDetailDto extends WorkspaceSummaryDto {
  reeDraft: Partial<ReeDraftDto>;
  files?: WorkspaceFileDto[];
}

export interface CreateWorkspaceRequestDto {
  sourceMode: "url" | "upload" | "demo";
  originUrl?: string;
  sourceType?: "git" | "tarball" | "zip";
  name?: string;
}

export interface PatchWorkspaceRequestDto {
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

export type WorkflowOperationDto =
  | "evaluate"
  | "build"
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
  workspaceId: string;
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
