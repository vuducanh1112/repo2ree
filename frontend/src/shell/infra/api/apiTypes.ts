import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";

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

export interface ReeIntentDto {
  name: string;
  catalog_metadata: {
    description?: string;
    version?: string;
    website?: string;
    keywords?: string[];
    contributors?: Array<{
      identifier?: string;
      name?: string;
      affiliation_name?: string;
      affiliation_identifier?: string;
    }>;
    corresponding_author_identifier?: string | null;
  };
  origin_url: string;
  source_type: string;
  runtime: string;
  runtime_entry?: Record<string, unknown>;
  sbom: string;
  build_runtime_script: string;
  activation?: Record<string, unknown>;
  swhid: string;
  zenodo_doi: string;
  dataverse_doi: string;
  hardware_description: Record<string, unknown>;
  experiments?: Array<Record<string, unknown>>;
}

export interface ReeSessionDto {
  sealed_at?: string;
  seal_hash?: string;
  dependency_level?: number;
  environment_level?: number;
  machine_level?: number;
  detected_dependencies?: string;
  source_available?: boolean;
  source_acquired_by?: string;
  uploaded_archive?: string;
  source_snapshot_archive?: string;
  source_snapshot_captured_at?: string;
  source_included?: boolean;
  runtime_included?: boolean;
}

export interface ReeDetailDto extends ReeSummaryDto {
  reeIntent: Partial<ReeIntentDto>;
  reeSession?: Partial<ReeSessionDto>;
  files?: ReeFileDto[];
  reeFiles?: ReeArtifactFileDto[];
  // The backend emits this already camelCased and the frontend renders it
  // untouched, so the wire shape and the domain type are one and the same.
  sourceRepo?: SourceRepoMetadata;
}

export interface CreateReeRequestDto {
  sourceMode: "url" | "upload";
  originUrl?: string;
  sourceType?: "git" | "tarball" | "zip";
  name?: string;
}

export interface PatchReeRequestDto {
  reeIntentPatch: Record<string, unknown>;
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
  | "hbom"
  | "sbom"
  | "activation"
  | "source"
  | "swh"
  | "zenodo"
  | "dataverse"
  | "experiment";

export interface CreateExperimentRunRequestDto {
  mode: "verify" | "snapshot";
}

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
  mode?: "verify" | "snapshot";
  idempotencyKey?: string;
}

export interface CreateEvaluateRunRequestDto {
  strict: boolean;
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
