export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface ApiListResponse<TItem> {
  items: TItem[];
  next_cursor?: string;
}

export interface ReeSummaryDto {
  ree_id: string;
  external_ref?: string;
  name: string;
  status: "draft" | "ready" | "sealed" | "archived";
  created_at: string;
  updated_at: string;
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
  lifecycle?: Record<string, unknown>;
  sbom: string;
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

/** Display-ready source-repository facts as they cross the wire (snake_case). */
export interface SourceRepoMetadataDto {
  name: string;
  origin: string;
  acquired_by: string;
  source_type: string;
  swhid: string;
  size_bytes: number | null;
  size_label: string | null;
}

export interface ConsistencyStaleInputDto {
  input: string;
  recorded: string | null;
  current: string | null;
}

export interface ConsistencyStepDto {
  step: string;
  status: "fresh" | "stale" | "missing";
  run_id?: string;
  recorded_at?: string;
  stale_inputs?: ConsistencyStaleInputDto[];
  workspace_drift?: "clean" | "modified" | "unknown";
}

/** Per-step freshness of recorded run receipts vs. the current tree. */
export interface ConsistencyReportDto {
  steps: ConsistencyStepDto[];
}

export interface ReeDetailDto extends ReeSummaryDto {
  ree_intent: Partial<ReeIntentDto>;
  ree_session?: Partial<ReeSessionDto>;
  files?: ReeFileDto[];
  ree_files?: ReeArtifactFileDto[];
  draft_manifest?: Record<string, unknown>;
  source_repo?: SourceRepoMetadataDto;
  consistency?: ConsistencyReportDto;
  /** The image this REE's workbench was provisioned from. */
  workbench_image?: string;
}

export interface CreateReeRequestDto {
  name?: string;
  /** Image to provision the workbench from; omitted falls back to the server default. */
  workbench_image?: string;
  /** Agent to place the workbench on (GET /agents); omitted means "any connected agent". */
  agent_id?: string;
}

/** A base image offered for workbench provisioning (GET /workbench/images). */
export interface WorkbenchImageDto {
  id: string;
  ref: string;
  label: string;
  description: string;
}

export interface WorkbenchImageCatalogDto {
  images: WorkbenchImageDto[];
  /** Id of the image used when a provisioning request omits one. */
  default_id: string;
}

/** One named starter-template variant for an REE-owned script; exactly one entry per list is the default. */
export interface ScriptTemplateEntryDto {
  key: string;
  label: string;
  description: string;
  body: string;
  is_default: boolean;
}

/** Backend-owned starter templates for the REE-owned scripts (GET /script-templates). */
export interface ScriptTemplateCatalogDto {
  build: {
    path: string;
    /** Named variants (currently only `docker`); the default is what a fresh REE is seeded with. */
    templates: ScriptTemplateEntryDto[];
  };
  activation: {
    run_script_path: string;
    /** Where an activation verify script belongs; declaring one is an explicit act. */
    verify_script_path: string;
    templates: ScriptTemplateEntryDto[];
  };
  experiment: {
    /** Path conventions with a `{slug}` placeholder (experiment name, whitespace → hyphens). */
    run_script_path_pattern: string;
    verify_script_path_pattern: string;
    templates: ScriptTemplateEntryDto[];
  };
  /** Verify templates shared across runnables. */
  verify: ScriptTemplateEntryDto[];
}

/** A workbench agent connected to the control plane (GET /agents). */
export interface AgentSummaryDto {
  agent_id: string;
  hostname: string;
  version: string;
  docker_mode: string;
  /** ISO 8601 UTC timestamp of when the agent dialed in. */
  connected_at: string;
  status: string;
}

export interface AgentListDto {
  agents: AgentSummaryDto[];
}

export interface PatchReeRequestDto {
  ree_intent_patch: Record<string, unknown>;
  expected_version?: string;
}

export interface SourceAcquireRequestDto {
  origin_url: string;
  source_type: "git" | "tarball" | "zip";
  /** Git revision (commit, branch, or tag) to pin the fetch to; blank means default-branch HEAD. */
  revision?: string;
}

/**
 * Shape an {@link SourceAcquireRequestDto} from loosely-typed download inputs,
 * applying the one normalization rule both acquire call sites (source execution
 * and workspace-reset fallback) must agree on: trim the revision and omit it
 * when blank, so the backend sees no revision rather than an empty string. Kept
 * here, next to the DTO, so the two paths cannot drift.
 */
export function toSourceAcquireRequest(input: {
  origin_url?: unknown;
  source_type?: unknown;
  revision?: unknown;
}): SourceAcquireRequestDto {
  const revision = typeof input.revision === "string" ? input.revision.trim() : "";
  return {
    origin_url: String(input.origin_url ?? ""),
    source_type: String(input.source_type ?? "git") as "git" | "tarball" | "zip",
    ...(revision ? { revision } : {}),
  };
}

export interface UploadInitRequestDto {
  file_name: string;
  size: number;
  content_type: string;
}

export interface UploadInitResponseDto {
  upload_url: string;
  upload_token: string;
  expires_at: string;
}

export type ReeRunOperationDto =
  | "provision"
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

// No fields yet — kept as the extension point for future run options.
export type CreateExperimentRunRequestDto = Record<string, never>;

export type ReeRunStatusDto =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

export interface CreateBuildRuntimeRunRequestDto {
  idempotency_key?: string;
}

export interface CreateGenerateSbomRunRequestDto {
  produced_runtime_path: string;
  idempotency_key?: string;
}

export interface CreateGenerateHbomRunRequestDto {
  idempotency_key?: string;
}

export interface CreateCrossCheckSbomRunRequestDto {
  idempotency_key?: string;
}

export interface CreateActivationTestRunRequestDto {
  idempotency_key?: string;
}

export interface CreateEvaluateRunRequestDto {
  strict: boolean;
  idempotency_key?: string;
}

export interface ReeRunDto {
  run_id: string;
  ree_id: string;
  operation: ReeRunOperationDto;
  status: ReeRunStatusDto;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  outputs?: Record<string, unknown>;
}

export interface ReeRunListDto {
  runs: ReeRunDto[];
}

export interface ReeRunLogEntryDto {
  seq: number;
  ts: string;
  stream: "stdout" | "stderr" | "system";
  level: "info" | "warn" | "error" | "debug";
  message: string;
}

export interface ReeRunLogsDto {
  entries: ReeRunLogEntryDto[];
  next_cursor?: string;
  has_more: boolean;
  run_status: ReeRunStatusDto;
}
